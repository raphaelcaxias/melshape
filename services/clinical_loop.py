"""
Melshape — Clinical Loop Service.

Fechar o loop clínico: quando o profissional age sobre um paciente
(conduta, prescrição, observação pública), o paciente é notificado
imediatamente e o evento é registrado na linha do tempo da jornada.

Problema resolvido:
    O profissional registra uma conduta e o único retorno é um toast
    para o próprio profissional. O paciente nunca sabe.

Solução:
    Toda ação do profissional sobre um paciente dispara:
    1. Notificação in-app na fila do paciente
    2. Registro na linha do tempo da jornada do paciente
    3. Email (se o paciente tiver notificações ativas)

Princípios:
- Loop fechado: toda ação do profissional gera uma reação no paciente
- Desacoplamento: o serviço usa apenas tabelas existentes
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para notificações

Tabelas utilizadas:
    - fila_notificacoes: notificações pendentes
    - eventos_jornada: linha do tempo da jornada
    - jornadas: jornada ativa do paciente

Arquitetura:
    ClinicalLoopService
    ├── Professional Actions
    │   ├── after_conduct(patient_id, conduct_info) -> NotificationResult
    │   ├── after_prescription(patient_id, objetivo, pro_nome) -> NotificationResult
    │   └── after_public_observation(patient_id, pro_nome) -> NotificationResult
    ├── Notification Pipeline
    │   ├── _execute_clinical_loop(patient_id, action) -> NotificationResult
    │   ├── _notify_patient(patient_id, action) -> bool
    │   ├── _register_journey_event(patient_id, action) -> bool
    │   └── _send_email(patient_id, action) -> bool
    └── Utilities
        ├── _get_patient_info(patient_id) -> PatientInfo | None
        ├── _get_patient_journey_id(patient_id) -> str | None
        └── generate_conduct_message(tipo, titulo, pro_nome) -> str
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import config
from core.database import Database
from services.email_service import send_clinical_action

logger = logging.getLogger("Melshape.ClinicalLoop")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Mapeamento de tipos de conduta para ícone e mensagem base
_CONDUCT_MESSAGES: dict[str, tuple[str, str]] = {
    "orientacao": ("📋", "Seu profissional registrou uma orientação para você"),
    "ajuste_dieta": ("🥗", "Seu profissional ajustou seu plano alimentar"),
    "alerta": ("⚠️", "Seu profissional deixou um alerta importante"),
    "encaminhamento": ("🏥", "Seu profissional fez um encaminhamento"),
    "elogio": ("🌟", "Seu profissional te elogiou — você está no caminho certo!"),
    "revisao": ("🔄", "Seu profissional revisou seu protocolo"),
    "prescricao": ("🥗", "Seu profissional criou uma nova prescrição alimentar"),
    "observacao": ("📝", "Seu profissional deixou uma anotação para você"),
}


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class ClinicalActionType(str, Enum):
    """Tipos de ações clínicas do profissional."""
    ORIENTACAO = "orientacao"
    AJUSTE_DIETA = "ajuste_dieta"
    ALERTA = "alerta"
    ENCAMINHAMENTO = "encaminhamento"
    ELOGIO = "elogio"
    REVISAO = "revisao"
    PRESCRICAO = "prescricao"
    OBSERVACAO = "observacao"
    
    @classmethod
    def from_string(cls, action_type: str) -> ClinicalActionType | None:
        """Converte string para ClinicalActionType."""
        try:
            return cls(action_type)
        except ValueError:
            return None
    
    @property
    def icon(self) -> str:
        """Retorna ícone do tipo de ação."""
        return _CONDUCT_MESSAGES.get(self.value, ("📋", ""))[0]
    
    @property
    def base_message(self) -> str:
        """Retorna mensagem base do tipo de ação."""
        return _CONDUCT_MESSAGES.get(self.value, ("📋", "Seu profissional agiu"))[1]


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO DE LOOP CLÍNICO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PatientInfo:
    """
    Informações básicas do paciente.
    
    Attributes:
        patient_id: ID do paciente
        email: Email do paciente
        name: Nome completo
        disable_reminders: Se o paciente desabilitou notificações
    """
    patient_id: str
    email: str = ""
    name: str = "Paciente"
    disable_reminders: bool = False
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatientInfo:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            patient_id=data.get("id", data.get("patient_id", "")),
            email=data.get("email", ""),
            name=data.get("nome_completo", data.get("name", "Paciente")),
            disable_reminders=data.get("disable_reminders", False),
        )
    
    @property
    def has_email(self) -> bool:
        """Verifica se o paciente tem email."""
        return bool(self.email and self.email.strip())
    
    @property
    def can_receive_emails(self) -> bool:
        """Verifica se o paciente pode receber emails."""
        return self.has_email and not self.disable_reminders


@dataclass(frozen=True)
class ClinicalAction:
    """
    Modelo unificado de ação clínica do profissional.
    
    Attributes:
        action_type: Tipo da ação
        title: Título/descrição da ação
        professional_name: Nome do profissional
        notification_type: Tipo da notificação (para fila)
        event_type: Tipo do evento (para jornada)
        event_description: Descrição do evento na jornada
        email_subject: Assunto do email
    """
    action_type: ClinicalActionType
    title: str
    professional_name: str = ""
    notification_type: str = "conduta_clinica"
    event_type: str = ""
    event_description: str = ""
    email_subject: str = ""
    
    @property
    def icon(self) -> str:
        """Retorna ícone da ação."""
        return self.action_type.icon
    
    @property
    def base_message(self) -> str:
        """Retorna mensagem base da ação."""
        return self.action_type.base_message
    
    @property
    def professional_suffix(self) -> str:
        """Retorna sufixo com nome do profissional."""
        return f" — {self.professional_name}" if self.professional_name else ""
    
    @property
    def notification_message(self) -> str:
        """Retorna mensagem completa para notificação."""
        return f"{self.icon} {self.base_message}{self.professional_suffix}: {self.title}"
    
    @property
    def full_event_description(self) -> str:
        """Retorna descrição completa para evento na jornada."""
        if self.event_description:
            return self.event_description
        return f"{self.action_type.icon} {self.title}"


@dataclass(frozen=True)
class NotificationResult:
    """
    Resultado do processo de notificação clínica.
    
    Attributes:
        success: Se o processo foi bem-sucedido
        patient_id: ID do paciente notificado
        notification_sent: Se notificação in-app foi criada
        journey_event_registered: Se evento foi registrado na jornada
        email_sent: Se email foi enviado
        action_type: Tipo da ação clínica
        message: Mensagem enviada
        error_message: Mensagem de erro (se houver)
    """
    success: bool = False
    patient_id: str = ""
    notification_sent: bool = False
    journey_event_registered: bool = False
    email_sent: bool = False
    action_type: str = ""
    message: str = ""
    error_message: str = ""
    
    @property
    def has_any_notification(self) -> bool:
        """Verifica se alguma notificação foi enviada."""
        return self.notification_sent or self.journey_event_registered or self.email_sent
    
    @property
    def notification_count(self) -> int:
        """Retorna quantidade de notificações enviadas."""
        return sum([
            self.notification_sent,
            self.journey_event_registered,
            self.email_sent,
        ])
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido do resultado."""
        parts = []
        if self.notification_sent:
            parts.append("📬 Notificação")
        if self.journey_event_registered:
            parts.append("📝 Evento na jornada")
        if self.email_sent:
            parts.append("📧 Email")
        
        if parts:
            return "Loop fechado: " + " + ".join(parts)
        return "Nenhuma notificação enviada"


# ─────────────────────────────────────────────────────────────────────────────
# CLINICAL LOOP SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class ClinicalLoopService:
    """
    Serviço de loop clínico fechado.
    
    Toda ação do profissional sobre um paciente gera notificação e evento.
    
    Example:
        >>> db = Database()
        >>> clinical_loop = ClinicalLoopService(db)
        >>> result = clinical_loop.after_conduct(
        ...     patient_id="patient_123",
        ...     titulo="Aumentar proteína",
        ...     tipo="orientacao",
        ...     pro_nome="Dr. João"
        ... )
        >>> print(result.summary_text)
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de loop clínico.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ ClinicalLoopService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # PROFESSIONAL ACTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def after_conduct(
        self,
        patient_id: str,
        titulo: str,
        tipo: str,
        pro_nome: str = "",
    ) -> NotificationResult:
        """
        Notifica paciente após uma conduta clínica.
        
        Args:
            patient_id: ID do paciente
            titulo: Título da conduta
            tipo: Tipo da conduta (orientacao/ajuste_dieta/alerta/etc)
            pro_nome: Nome do profissional
            
        Returns:
            Objeto NotificationResult com resultado do processo
            
        Example:
            >>> result = clinical_loop.after_conduct(
            ...     patient_id="patient_123",
            ...     titulo="Aumentar proteína para 1.8g/kg",
            ...     tipo="orientacao",
            ...     pro_nome="Dra. Ana"
            ... )
            >>> print(result.summary_text)
        """
        if not patient_id or not titulo:
            logger.warning("after_conduct: patient_id ou titulo não informados")
            return NotificationResult(
                success=False,
                error_message="patient_id ou titulo não informados",
            )
        
        # Converte tipo para enum
        action_type = ClinicalActionType.from_string(tipo)
        if not action_type:
            logger.warning(f"after_conduct: tipo inválido: {tipo}")
            action_type = ClinicalActionType.ORIENTACAO
        
        # Cria ação clínica
        action = ClinicalAction(
            action_type=action_type,
            title=titulo,
            professional_name=pro_nome,
            notification_type="conduta_clinica",
            event_type=f"conduta_{tipo}",
            event_description=f"Conduta: {titulo}",
        )
        
        # Executa loop clínico
        return self._execute_clinical_loop(patient_id, action)

    def after_prescription(
        self,
        patient_id: str,
        objetivo: str,
        pro_nome: str = "",
    ) -> NotificationResult:
        """
        Notifica paciente após uma prescrição alimentar.
        
        Args:
            patient_id: ID do paciente
            objetivo: Objetivo da prescrição
            pro_nome: Nome do profissional
            
        Returns:
            Objeto NotificationResult com resultado do processo
            
        Example:
            >>> result = clinical_loop.after_prescription(
            ...     patient_id="patient_123",
            ...     objetivo="Déficit calórico moderado com alta proteína",
            ...     pro_nome="Dra. Ana"
            ... )
            >>> print(result.summary_text)
        """
        if not patient_id or not objetivo:
            logger.warning("after_prescription: patient_id ou objetivo não informados")
            return NotificationResult(
                success=False,
                error_message="patient_id ou objetivo não informados",
            )
        
        # Cria ação clínica
        action = ClinicalAction(
            action_type=ClinicalActionType.PRESCRICAO,
            title=objetivo,
            professional_name=pro_nome,
            notification_type="prescricao",
            event_type="prescricao",
            event_description=f"Prescrição: {objetivo}",
            email_subject=f"Nova prescrição: {objetivo}",
        )
        
        # Executa loop clínico
        return self._execute_clinical_loop(patient_id, action)

    def after_public_observation(
        self,
        patient_id: str,
        pro_nome: str = "",
    ) -> NotificationResult:
        """
        Notifica paciente após uma observação pública.
        
        Args:
            patient_id: ID do paciente
            pro_nome: Nome do profissional
            
        Returns:
            Objeto NotificationResult com resultado do processo
            
        Example:
            >>> result = clinical_loop.after_public_observation(
            ...     patient_id="patient_123",
            ...     pro_nome="Dra. Ana"
            ... )
            >>> print(result.summary_text)
        """
        if not patient_id:
            logger.warning("after_public_observation: patient_id não informado")
            return NotificationResult(
                success=False,
                error_message="patient_id não informado",
            )
        
        # Cria ação clínica
        action = ClinicalAction(
            action_type=ClinicalActionType.OBSERVACAO,
            title="Observação pública registrada",
            professional_name=pro_nome,
            notification_type="observacao",
            event_type="observacao_publica",
            event_description="Observação pública registrada",
            email_subject="Nova observação pública",
        )
        
        # Executa loop clínico
        return self._execute_clinical_loop(patient_id, action)

    # ─────────────────────────────────────────────────────────────────────────
    # NOTIFICATION PIPELINE
    # ─────────────────────────────────────────────────────────────────────────

    def _execute_clinical_loop(
        self,
        patient_id: str,
        action: ClinicalAction,
    ) -> NotificationResult:
        """
        Executa o loop clínico completo para uma ação.
        
        Pipeline:
        1. Notificação in-app
        2. Evento na jornada
        3. Email (se paciente permitir)
        
        Args:
            patient_id: ID do paciente
            action: Ação clínica a ser processada
            
        Returns:
            Objeto NotificationResult com resultado do processo
        """
        result = NotificationResult(
            patient_id=patient_id,
            action_type=action.action_type.value,
            message=action.notification_message,
        )
        
        try:
            # 1. Notificação in-app
            result.notification_sent = self._notify_patient(patient_id, action)
            
            # 2. Evento na jornada
            result.journey_event_registered = self._register_journey_event(patient_id, action)
            
            # 3. Email (se paciente permitir)
            result.email_sent = self._send_email(patient_id, action)
            
            # Determina sucesso
            result.success = result.has_any_notification
            
            if result.success:
                logger.info(
                    f"✅ Loop clínico fechado: {action.action_type.value} para {patient_id} "
                    f"({result.notification_count} notificações)"
                )
            else:
                logger.warning(f"⚠️ Loop clínico falhou para {patient_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"_execute_clinical_loop falhou: {e}", exc_info=True)
            result.error_message = str(e)
            return result

    def _notify_patient(
        self,
        patient_id: str,
        action: ClinicalAction,
    ) -> bool:
        """
        Cria notificação in-app na fila do paciente.
        
        Nota: Insere diretamente na tabela porque o método create_notification
        do Database usa self.uid() que seria o profissional neste contexto.
        
        Args:
            patient_id: ID do paciente
            action: Ação clínica
            
        Returns:
            True se notificação criada com sucesso
        """
        if not patient_id:
            logger.warning("_notify_patient: patient_id não informado")
            return False
        
        mensagem = action.notification_message
        tipo = action.notification_type
        
        if not (self.db.is_real and self.db.client):
            logger.info(f"[MOCK] Notificação in-app para {patient_id}: {mensagem[:60]}...")
            return True
        
        try:
            self.db.client.table("fila_notificacoes").insert({
                "perfil_id": patient_id,
                "mensagem": mensagem,
                "tipo": tipo,
                "enviada": False,
            }).execute()
            
            logger.debug(f"✅ Notificação in-app criada para {patient_id}")
            return True
            
        except Exception as e:
            logger.error(f"_notify_patient: {e}")
            return False

    def _register_journey_event(
        self,
        patient_id: str,
        action: ClinicalAction,
    ) -> bool:
        """
        Registra evento na linha do tempo da jornada do paciente.
        
        Args:
            patient_id: ID do paciente
            action: Ação clínica
            
        Returns:
            True se registrado com sucesso
        """
        if not patient_id:
            logger.warning("_register_journey_event: patient_id não informado")
            return False
        
        if not (self.db.is_real and self.db.client):
            return True
        
        try:
            # Busca jornada ativa do paciente
            journey_id = self._get_patient_journey_id(patient_id)
            
            if not journey_id:
                logger.debug(f"_register_journey_event: paciente {patient_id} sem jornada ativa")
                return False
            
            # Registra evento
            self.db.client.table("eventos_jornada").insert({
                "jornada_id": journey_id,
                "tipo": action.event_type,
                "descricao": action.full_event_description,
            }).execute()
            
            logger.debug(f"✅ Evento registrado na jornada: {action.full_event_description[:50]}...")
            return True
            
        except Exception as e:
            logger.warning(f"_register_journey_event: {e}")
            return False

    def _send_email(
        self,
        patient_id: str,
        action: ClinicalAction,
    ) -> bool:
        """
        Envia email ao paciente (se permitido).
        
        Args:
            patient_id: ID do paciente
            action: Ação clínica
            
        Returns:
            True se enviado com sucesso
        """
        if not patient_id:
            logger.warning("_send_email: patient_id não informado")
            return False
        
        # Busca informações do paciente
        patient_info = self._get_patient_info(patient_id)
        
        if not patient_info:
            logger.debug(f"_send_email: paciente {patient_id} não encontrado")
            return False
        
        if not patient_info.can_receive_emails:
            logger.debug(f"_send_email: paciente {patient_id} não pode receber emails")
            return False
        
        # Determina assunto
        subject = action.email_subject if action.email_subject else action.title
        
        try:
            result = send_clinical_action(
                patient_info.email,
                patient_info.name,
                subject,
                action.notification_message,
            )
            
            if result:
                logger.info(f"✅ Email clínico enviado para {patient_info.email}")
            else:
                logger.warning(f"❌ Falha ao enviar email para {patient_info.email}")
            
            return result
            
        except Exception as e:
            logger.error(f"_send_email: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def _get_patient_info(self, patient_id: str) -> PatientInfo | None:
        """
        Busca informações completas do paciente.
        
        Args:
            patient_id: ID do paciente
            
        Returns:
            Objeto PatientInfo ou None
        """
        if not patient_id:
            logger.warning("_get_patient_info: patient_id não informado")
            return None
        
        if not (self.db.is_real and self.db.client):
            return None
        
        try:
            response = (
                self.db.client.table("perfis")
                .select("id, email, nome_completo, disable_reminders")
                .eq("id", patient_id)
                .limit(1)
                .execute()
            )
            
            if response.data:
                return PatientInfo.from_dict(response.data[0])
            
            logger.debug(f"_get_patient_info: paciente {patient_id} não encontrado")
            return None
            
        except Exception as e:
            logger.warning(f"_get_patient_info: {e}")
            return None

    def _get_patient_journey_id(self, patient_id: str) -> str | None:
        """
        Busca ID da jornada ativa do paciente.
        
        Args:
            patient_id: ID do paciente
            
        Returns:
            ID da jornada ou None
        """
        if not patient_id:
            return None
        
        if not (self.db.is_real and self.db.client):
            return None
        
        try:
            response = (
                self.db.client.table("jornadas")
                .select("id")
                .eq("perfil_id", patient_id)
                .eq("ativa", True)
                .limit(1)
                .execute()
            )
            
            if response.data:
                return response.data[0]["id"]
            
            return None
            
        except Exception as e:
            logger.warning(f"_get_patient_journey_id: {e}")
            return None

    def generate_conduct_message(
        self,
        tipo: str,
        titulo: str,
        pro_nome: str = "",
    ) -> str:
        """
        Gera mensagem formatada para uma conduta.
        
        Args:
            tipo: Tipo da conduta
            titulo: Título da conduta
            pro_nome: Nome do profissional
            
        Returns:
            Mensagem formatada
            
        Example:
            >>> msg = clinical_loop.generate_conduct_message(
            ...     "orientacao",
            ...     "Aumentar proteína",
            ...     "Dra. Ana"
            ... )
            >>> print(msg)
        """
        action_type = ClinicalActionType.from_string(tipo)
        if not action_type:
            action_type = ClinicalActionType.ORIENTACAO
        
        action = ClinicalAction(
            action_type=action_type,
            title=titulo,
            professional_name=pro_nome,
        )
        
        return action.notification_message


__all__ = [
    "ClinicalLoopService",
    "ClinicalActionType",
    "PatientInfo",
    "ClinicalAction",
    "NotificationResult",
]
