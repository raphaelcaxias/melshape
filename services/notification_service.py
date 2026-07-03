"""
Melshape — Notification Service.

Serviço de notificações in-app, anti-abandono e lembretes contextuais.

Modos de operação:
1. In-app: notificações via fila_notificacoes (Supabase) exibidas como toasts
2. Contextuais: geradas a cada acesso à home (streak em risco, meta próxima, hábito pendente)
3. Anti-abandono: verificação de risco via vw_pacientes_para_notificar
4. Agendadas: APScheduler em background (20h lembretes, 9h trial)
5. Manual: send_manual_reminder() para envio direto

Princípios:
- Nunca punir: mensagens são acolhedoras e motivacionais
- Contextuais: notificações relevantes para o momento do paciente
- Proativas: o sistema busca o paciente, não espera ele aparecer
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    NotificationService
    ├── Inbox
    │   ├── get_inbox(limit) -> list[InAppNotification]
    │   ├── get_unread_count() -> int
    │   ├── mark_as_read(notif_id) -> bool
    │   ├── mark_as_delivered(notif_id) -> bool
    │   └── deliver_pending(user) -> list[InAppNotification]
    ├── Creation
    │   ├── create_notification(message, type, user_id) -> InAppNotification | None
    │   └── create_bulk_notifications(messages, type, user_ids) -> int
    ├── Contextual
    │   ├── check_streak_risk(user) -> str | None
    │   ├── check_goal_deadline(user) -> str | None
    │   ├── check_pending_habits(user) -> str | None
    │   ├── check_abandonment_risk(user) -> str | None
    │   └── generate_contextual_notifications(user) -> list[InAppNotification]
    ├── Anti-abandonment
    │   ├── patients_at_risk(limit) -> list[RiskPatient]
    │   ├── professional_actions() -> list[ProfessionalAction]
    │   └── clinical_summary() -> ClinicalSummary
    ├── Scheduled (APScheduler)
    │   └── schedule_daily_reminders(db) -> BackgroundScheduler | None
    ├── Manual
    │   └── send_manual_reminder(email, name, db) -> bool
    └── History
        └── get_notification_history(limit) -> list[InAppNotification]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import streamlit as st

import config
from core.database import Database
from services.email_service import send_meal_reminder, send_streak_at_risk, send_trial_expiring
from services.goals_service import GoalsService
from services.journey_service import JourneyService

logger = logging.getLogger("Melshape.Notifications")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Tipos de notificação
NOTIFICATION_TYPES: dict[str, dict[str, str]] = {
    "engajamento": {"icon": "💬", "label": "Engajamento"},
    "streak_risco": {"icon": "🔥", "label": "Streak em Risco"},
    "meta_proxima": {"icon": "🎯", "label": "Meta Próxima"},
    "habito_pendente": {"icon": "📋", "label": "Hábito Pendente"},
    "jornada_avanco": {"icon": "🗺️", "label": "Jornada"},
    "risco_abandono": {"icon": "😔", "label": "Risco de Abandono"},
    "sem_checkin": {"icon": "⚡", "label": "Check-in Pendente"},
    "conduta_clinica": {"icon": "📋", "label": "Conduta Clínica"},
    "prescricao": {"icon": "🥗", "label": "Prescrição"},
    "observacao": {"icon": "📝", "label": "Observação"},
    "recomeco": {"icon": "🌱", "label": "Recomeço"},
}

# Horários padrão (configuráveis via env)
_DEFAULT_REMINDER_HOUR: int = getattr(config, "NOTIFICATION_REMINDER_HOUR", 20)
_DEFAULT_TRIAL_HOUR: int = getattr(config, "NOTIFICATION_TRIAL_HOUR", 9)

# Dias para verificação de abandono
_ABANDONMENT_CHECK_DAYS: int = 7
_ABANDONMENT_CRITICAL_DAYS: int = 5

# Limites de notificações
_MAX_INBOX: int = 20
_MAX_HISTORY: int = 50
_MAX_RISK_PATIENTS: int = 10

# Thresholds de contexto
_STREAK_RISK_MIN: int = 3
_PENDING_HABITS_HOUR: int = 18
_GOAL_DEADLINE_DAYS: int = 3


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO DE NOTIFICAÇÕES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class InAppNotification:
    """
    Modelo de notificação in-app.
    
    Attributes:
        id: ID único da notificação
        user_id: ID do usuário
        message: Mensagem da notificação
        type: Tipo da notificação
        read: Se foi lida
        delivered: Se foi entregue
        created_at: Timestamp de criação
    """
    id: str
    user_id: str
    message: str
    type: str = "engajamento"
    read: bool = False
    delivered: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InAppNotification:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            message=data.get("mensagem", data.get("message", "")),
            type=data.get("tipo", data.get("type", "engajamento")),
            read=data.get("lida", data.get("read", False)),
            delivered=data.get("enviada", data.get("delivered", False)),
            created_at=data.get("criado_em", data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )
    
    @property
    def icon(self) -> str:
        """Retorna ícone do tipo de notificação."""
        return NOTIFICATION_TYPES.get(self.type, {}).get("icon", "💬")
    
    @property
    def type_label(self) -> str:
        """Retorna label do tipo de notificação."""
        return NOTIFICATION_TYPES.get(self.type, {}).get("label", self.type)
    
    @property
    def is_read(self) -> bool:
        """Verifica se foi lida."""
        return self.read
    
    @property
    def is_unread(self) -> bool:
        """Verifica se não foi lida."""
        return not self.read
    
    @property
    def is_delivered(self) -> bool:
        """Verifica se foi entregue."""
        return self.delivered
    
    @property
    def is_pending(self) -> bool:
        """Verifica se está pendente (não entregue)."""
        return not self.delivered
    
    @property
    def time_ago(self) -> str:
        """Retorna tempo decorrido desde a criação."""
        try:
            created = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            delta = now - created
            
            if delta.days > 0:
                return f"{delta.days}d atrás"
            elif delta.seconds >= 3600:
                hours = delta.seconds // 3600
                return f"{hours}h atrás"
            elif delta.seconds >= 60:
                minutes = delta.seconds // 60
                return f"{minutes}min atrás"
            return "agora"
        except Exception:
            return ""
    
    @property
    def display_message(self) -> str:
        """Retorna mensagem formatada para exibição."""
        return f"{self.icon} {self.message}"


@dataclass(frozen=True)
class RiskPatient:
    """
    Modelo de paciente em risco de abandono.
    
    Attributes:
        patient_id: ID do paciente
        name: Nome do paciente
        days_without_access: Dias sem acesso
        days_without_checkin: Dias sem check-in
        reason: Motivo do risco
    """
    patient_id: str
    name: str
    days_without_access: int = 0
    days_without_checkin: int = 0
    reason: str = ""
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskPatient:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            patient_id=data.get("perfil_id", ""),
            name=data.get("nome_completo", ""),
            days_without_access=int(data.get("dias_sem_acesso", 0)),
            days_without_checkin=int(data.get("dias_sem_checkin", 0)),
            reason=data.get("motivo", ""),
        )
    
    @property
    def is_critical(self) -> bool:
        """Verifica se é risco crítico."""
        return self.reason == "RISCO_ABANDONO" and self.days_without_checkin >= _ABANDONMENT_CRITICAL_DAYS
    
    @property
    def is_warning(self) -> bool:
        """Verifica se é risco moderado."""
        return self.reason == "RISCO_ABANDONO" and self.days_without_checkin < _ABANDONMENT_CRITICAL_DAYS
    
    @property
    def urgency_label(self) -> str:
        """Retorna label de urgência."""
        if self.is_critical:
            return "🚨 Alta"
        elif self.is_warning:
            return "⚠️ Média"
        return "📋 Baixa"


@dataclass(frozen=True)
class ProfessionalAction:
    """
    Modelo de ação recomendada para o profissional.
    
    Attributes:
        patient_name: Nome do paciente
        patient_id: ID do paciente
        reason: Motivo da ação
        action: Ação recomendada
        urgency: Nível de urgência (alta/media/baixa)
        icon: Ícone representativo
    """
    patient_name: str
    patient_id: str
    reason: str
    action: str
    urgency: str = "baixa"
    icon: str = "📋"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfessionalAction:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            patient_name=data.get("paciente", ""),
            patient_id=data.get("perfil_id", ""),
            reason=data.get("motivo", ""),
            action=data.get("acao", ""),
            urgency=data.get("urgencia", "baixa"),
            icon=data.get("icone", "📋"),
        )
    
    @property
    def is_urgent(self) -> bool:
        """Verifica se é ação urgente."""
        return self.urgency == "alta"
    
    @property
    def display_text(self) -> str:
        """Retorna texto formatado para exibição."""
        return f"{self.icon} {self.patient_name}: {self.action}"


@dataclass(frozen=True)
class ClinicalSummary:
    """
    Modelo de resumo clínico para gestores.
    
    Attributes:
        total: Total de pacientes em risco
        by_reason: Contagem por motivo
        recommendation: Recomendação geral
    """
    total: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)
    recommendation: str = ""
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClinicalSummary:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            total=int(data.get("total", 0)),
            by_reason=data.get("por_motivo", {}),
            recommendation=data.get("recomendacao", ""),
        )
    
    @property
    def has_risk(self) -> bool:
        """Verifica se há pacientes em risco."""
        return self.total > 0
    
    @property
    def is_critical(self) -> bool:
        """Verifica se é situação crítica."""
        return self.total >= 10
    
    @property
    def is_moderate(self) -> bool:
        """Verifica se é situação moderada."""
        return 5 <= self.total < 10


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class NotificationService:
    """
    Serviço de notificações in-app, anti-abandono e lembretes contextuais.
    
    Example:
        >>> db = Database()
        >>> notification_service = NotificationService(db)
        >>> user = st.session_state.user
        >>> inbox = notification_service.get_inbox(limit=5)
        >>> for n in inbox:
        ...     print(f"{n.icon} {n.message}")
        ...     if n.time_ago:
        ...         print(f"  {n.time_ago}")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de notificações.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ NotificationService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # INBOX (Fila e Histórico)
    # ─────────────────────────────────────────────────────────────────────────

    def get_inbox(self, limit: int = _MAX_INBOX) -> list[InAppNotification]:
        """
        Retorna notificações não lidas do usuário.
        
        Args:
            limit: Número máximo de notificações
            
        Returns:
            Lista de objetos InAppNotification (ordenadas por data descendente)
            
        Example:
            >>> inbox = notification_service.get_inbox(limit=5)
            >>> for n in inbox:
            ...     print(f"{n.icon} {n.message}")
        """
        if limit <= 0:
            logger.warning(f"get_inbox: limit inválido: {limit}")
            return []
        
        try:
            # Busca pendentes
            pending = self.db.get_pending_notifications(limit=limit)
            
            # Converte para objetos InAppNotification
            notifications = [InAppNotification.from_dict(n) for n in pending]
            
            logger.debug(f"✅ {len(notifications)} notificações na inbox")
            return notifications
            
        except Exception as e:
            logger.error(f"get_inbox falhou: {e}")
            return []

    def get_unread_count(self) -> int:
        """
        Retorna quantidade de notificações não lidas.
        
        Returns:
            Número de notificações não lidas
            
        Example:
            >>> count = notification_service.get_unread_count()
            >>> print(f"Você tem {count} notificações não lidas")
        """
        try:
            notifications = self.get_inbox(limit=100)
            count = sum(1 for n in notifications if n.is_unread)
            logger.debug(f"✅ {count} notificações não lidas")
            return count
        except Exception as e:
            logger.error(f"get_unread_count falhou: {e}")
            return 0

    def mark_as_read(self, notif_id: str) -> bool:
        """
        Marca uma notificação como lida.
        
        Args:
            notif_id: ID da notificação
            
        Returns:
            True se marcada com sucesso
            
        Example:
            >>> notification_service.mark_as_read("notif_123")
            True
        """
        if not notif_id:
            logger.warning("mark_as_read: notif_id não informado")
            return False
        
        try:
            # Marca como entregue no banco
            success = self.db.mark_as_delivered(notif_id)
            
            if success:
                logger.debug(f"✅ Notificação marcada como lida: {notif_id}")
            else:
                logger.warning(f"❌ Falha ao marcar notificação: {notif_id}")
            
            return success
        except Exception as e:
            logger.error(f"mark_as_read falhou: {e}")
            return False

    def mark_as_delivered(self, notif_id: str) -> bool:
        """
        Marca uma notificação como entregue.
        
        Alias para mark_as_read para compatibilidade semântica.
        
        Args:
            notif_id: ID da notificação
            
        Returns:
            True se marcada com sucesso
        """
        return self.mark_as_read(notif_id)

    def create_notification(
        self,
        message: str,
        type: str = "engajamento",
        user_id: str | None = None,
    ) -> InAppNotification | None:
        """
        Cria uma nova notificação.
        
        Args:
            message: Mensagem da notificação
            type: Tipo da notificação
            user_id: ID do usuário (padrão: usuário logado)
            
        Returns:
            Objeto InAppNotification criado ou None se falhar
            
        Example:
            >>> notification = notification_service.create_notification(
            ...     "🔥 Você está a 1 dia de completar 7 dias seguidos!",
            ...     "streak_risco"
            ... )
            >>> if notification:
            ...     print(f"Notificação criada: {notification.id}")
        """
        if not message:
            logger.warning("create_notification: message não informado")
            return None
        
        if not type:
            logger.warning("create_notification: type não informado")
            return None
        
        try:
            # Se user_id não informado, usa o usuário logado
            if not user_id:
                user_id = self.db.uid()
            
            # Cria no banco
            success = self.db.create_notification(message, tipo=type)
            
            if success:
                # Busca a notificação criada (última)
                notifications = self.db.get_pending_notifications(limit=1)
                if notifications:
                    notification = InAppNotification.from_dict(notifications[0])
                    logger.info(f"✅ Notificação criada: {type} - {message[:50]}...")
                    return notification
            
            logger.warning(f"❌ Falha ao criar notificação: {type}")
            return None
            
        except Exception as e:
            logger.error(f"create_notification falhou: {e}")
            return None

    def create_bulk_notifications(
        self,
        messages: list[str],
        type: str = "engajamento",
        user_id: str | None = None,
    ) -> int:
        """
        Cria múltiplas notificações.
        
        Args:
            messages: Lista de mensagens
            type: Tipo das notificações
            user_id: ID do usuário
            
        Returns:
            Número de notificações criadas
            
        Example:
            >>> count = notification_service.create_bulk_notifications(
            ...     ["Mensagem 1", "Mensagem 2"],
            ...     "engajamento"
            ... )
            >>> print(f"{count} notificações criadas")
        """
        if not messages:
            logger.warning("create_bulk_notifications: messages vazio")
            return 0
        
        created = 0
        for message in messages:
            notification = self.create_notification(message, type, user_id)
            if notification:
                created += 1
        
        logger.info(f"✅ {created}/{len(messages)} notificações criadas")
        return created

    # ─────────────────────────────────────────────────────────────────────────
    # CONTEXTUAIS (geradas a cada acesso)
    # ─────────────────────────────────────────────────────────────────────────

    def check_streak_risk(self, user: dict[str, Any] | Any) -> str | None:
        """
        Verifica se o paciente tem streak ativo mas ainda não fez check-in hoje.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Mensagem de notificação ou None
            
        Example:
            >>> msg = notification_service.check_streak_risk(user)
            >>> if msg:
            ...     notification_service.create_notification(msg, "streak_risco")
        """
        if not user:
            logger.warning("check_streak_risk: user não informado")
            return None
        
        try:
            streak = self.db.get_checkin_streak()
            checkin_today = self.db.get_checkin_today()
            
            # Streak >= 3 e ainda não fez check-in hoje
            if streak >= _STREAK_RISK_MIN and not checkin_today:
                nome = self._get_first_name(user)
                return (
                    f"🔥 {nome}, sua sequência de {streak} dias está esperando "
                    f"o check-in de hoje. Não quebre agora!"
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"check_streak_risk falhou: {e}")
            return None

    def check_goal_deadline(self, user: dict[str, Any] | Any) -> str | None:
        """
        Verifica se alguma meta ativa está a 3 dias ou menos do prazo.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Mensagem de notificação ou None
            
        Example:
            >>> msg = notification_service.check_goal_deadline(user)
            >>> if msg:
            ...     notification_service.create_notification(msg, "meta_proxima")
        """
        if not user:
            logger.warning("check_goal_deadline: user não informado")
            return None
        
        try:
            # Busca jornada ativa
            journey_service = JourneyService(self.db)
            journey = journey_service.ensure_journey(user)
            journey_id = journey.id if hasattr(journey, "id") else journey.get("id", "")
            
            if not journey_id:
                return None
            
            goals_service = GoalsService(self.db)
            goals = self.db.get_goals(journey_id)
            
            for goal in goals:
                # Verifica se é objeto ou dict
                is_completed = goal.concluida if hasattr(goal, "concluida") else goal.get("concluida", False)
                if is_completed:
                    continue
                
                prazo = goal.prazo if hasattr(goal, "prazo") else goal.get("prazo")
                if not prazo:
                    continue
                
                days = goals_service.days_remaining(prazo)
                
                if days is not None and 0 <= days <= _GOAL_DEADLINE_DAYS:
                    titulo = goal.titulo if hasattr(goal, "titulo") else goal.get("titulo", "Meta")
                    return (
                        f"🎯 Faltam {days} dia(s) para o prazo de "
                        f'"{titulo}". Você consegue!'
                    )
            
            return None
            
        except Exception as e:
            logger.warning(f"check_goal_deadline falhou: {e}")
            return None

    def check_pending_habits(self, user: dict[str, Any] | Any) -> str | None:
        """
        Verifica se já é tarde do dia e ainda há hábitos pendentes.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Mensagem de notificação ou None
            
        Example:
            >>> msg = notification_service.check_pending_habits(user)
            >>> if msg:
            ...     notification_service.create_notification(msg, "habito_pendente")
        """
        if not user:
            logger.warning("check_pending_habits: user não informado")
            return None
        
        try:
            # Só avisa a partir do fim da tarde (18h)
            now = datetime.now()
            if now.hour < _PENDING_HABITS_HOUR:
                return None
            
            habits = self.db.get_habits()
            done_today = self.db.get_today_records()
            
            pending = [h for h in habits if h.id not in done_today]
            
            if pending:
                n = len(pending)
                return (
                    f"📋 Você ainda tem {n} hábito(s) pendente(s) hoje. "
                    f"Pequenas ações consistentes fazem a diferença."
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"check_pending_habits falhou: {e}")
            return None

    def check_abandonment_risk(self, user: dict[str, Any] | Any) -> str | None:
        """
        Verifica risco de abandono via vw_pacientes_para_notificar.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Mensagem de notificação ou None
            
        Example:
            >>> msg = notification_service.check_abandonment_risk(user)
            >>> if msg:
            ...     notification_service.create_notification(msg, "risco_abandono")
        """
        if not user:
            logger.warning("check_abandonment_risk: user não informado")
            return None
        
        if not self.db.is_real or not self.db.client:
            return None
        
        try:
            uid = self.db.uid()
            
            response = (
                self.db.client.table("vw_pacientes_para_notificar")
                .select("motivo, dias_sem_checkin")
                .eq("perfil_id", uid)
                .limit(1)
                .execute()
            )
            
            if not response.data:
                return None
            
            row = response.data[0]
            motivo = row.get("motivo", "")
            dias = int(row.get("dias_sem_checkin") or 0)
            nome = self._get_first_name(user)
            
            return self._generate_abandonment_message(motivo, dias, nome)
            
        except Exception as e:
            logger.warning(f"check_abandonment_risk falhou: {e}")
            return None

    def _generate_abandonment_message(self, motivo: str, dias: int, nome: str) -> str | None:
        """
        Gera mensagem de abandono personalizada.
        
        Args:
            motivo: Motivo do risco
            dias: Dias sem check-in
            nome: Nome do paciente
            
        Returns:
            Mensagem personalizada
        """
        if motivo == "RISCO_ABANDONO":
            if dias >= _ABANDONMENT_CHECK_DAYS:
                return (
                    f"😔 {nome}, sentimos sua falta! {dias} dias sem check-in. "
                    f"Seu corpo e sua mente agradecem por cada recomeço — "
                    f"estamos aqui para te apoiar."
                )
            return (
                f"⚡ {nome}, sua sequência anterior provou que você consegue. "
                f"Vamos retomar juntos?"
            )
        
        if motivo == "SEM_CHECKIN":
            return (
                f"✅ {nome}, seu check-in de hoje está esperando. "
                f"30 segundos mantêm sua sequência ativa."
            )
        
        return None

    def generate_contextual_notifications(self, user: dict[str, Any] | Any) -> list[InAppNotification]:
        """
        Gera todas as notificações contextuais para o usuário.
        
        Combina todos os checks contextuais e cria notificações automaticamente.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Lista de notificações criadas
            
        Example:
            >>> notifications = notification_service.generate_contextual_notifications(user)
            >>> for n in notifications:
            ...     print(f"{n.icon} {n.message}")
        """
        if not user:
            logger.warning("generate_contextual_notifications: user não informado")
            return []
        
        notifications = []
        
        # Check streak risk
        msg = self.check_streak_risk(user)
        if msg:
            notif = self.create_notification(msg, "streak_risco")
            if notif:
                notifications.append(notif)
        
        # Check goal deadline
        msg = self.check_goal_deadline(user)
        if msg:
            notif = self.create_notification(msg, "meta_proxima")
            if notif:
                notifications.append(notif)
        
        # Check pending habits
        msg = self.check_pending_habits(user)
        if msg:
            notif = self.create_notification(msg, "habito_pendente")
            if notif:
                notifications.append(notif)
        
        # Check abandonment risk
        msg = self.check_abandonment_risk(user)
        if msg:
            notif = self.create_notification(msg, "risco_abandono")
            if notif:
                notifications.append(notif)
        
        if notifications:
            logger.info(f"✅ {len(notifications)} notificações contextuais geradas")
        
        return notifications

    def deliver_pending(self, user: dict[str, Any] | Any) -> list[InAppNotification]:
        """
        Entrega notificações pendentes via st.toast().
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Lista de notificações entregues
            
        Example:
            >>> notifications = notification_service.deliver_pending(user)
            >>> for n in notifications:
            ...     st.toast(f"{n.icon} {n.message}")
        """
        if not user:
            logger.warning("deliver_pending: user não informado")
            return []
        
        try:
            # Busca pendentes
            pending = self.db.get_pending_notifications(limit=5)

            notifications = [InAppNotification.from_dict(n) for n in pending]

            # Sprint 5 — batch update: 1 query ao invés de N
            if notifications:
                ids = [n.id for n in notifications if n.id]
                if hasattr(self.db, "mark_all_delivered"):
                    self.db.mark_all_delivered(ids)
                else:
                    for n in notifications:
                        self.db.mark_as_delivered(n.id)

                for n in notifications:
                    st.toast(n.display_message)

                logger.info(f"✅ {len(notifications)} notificações entregues (batch)")

            return notifications

        except Exception as e:
            logger.error(f"deliver_pending falhou: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # HISTORY
    # ─────────────────────────────────────────────────────────────────────────

    def get_notification_history(self, limit: int = _MAX_HISTORY) -> list[InAppNotification]:
        """
        Retorna histórico de notificações (entregues).
        
        Args:
            limit: Número máximo de notificações
            
        Returns:
            Lista de objetos InAppNotification (ordenadas por data descendente)
            
        Example:
            >>> history = notification_service.get_notification_history(limit=20)
            >>> for n in history:
            ...     print(f"{n.icon} {n.message} - {n.time_ago}")
        """
        if limit <= 0:
            logger.warning(f"get_notification_history: limit inválido: {limit}")
            return []
        
        try:
            history = self.db.get_notification_history(days=30)
            notifications = [InAppNotification.from_dict(n) for n in history]
            
            # Ordena por data descendente
            notifications.sort(key=lambda x: x.created_at, reverse=True)
            
            logger.debug(f"✅ {len(notifications)} notificações no histórico")
            return notifications[:limit]
            
        except Exception as e:
            logger.error(f"get_notification_history falhou: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # PATIENTS AT RISK (visão do profissional)
    # ─────────────────────────────────────────────────────────────────────────

    def patients_at_risk(self, limit: int = _MAX_RISK_PATIENTS) -> list[RiskPatient]:
        """
        Lista pacientes em risco via vw_pacientes_para_notificar.
        
        Args:
            limit: Número máximo de pacientes
            
        Returns:
            Lista de objetos RiskPatient
            
        Example:
            >>> at_risk = notification_service.patients_at_risk(limit=10)
            >>> for p in at_risk:
            ...     print(f"{p.name} - {p.reason}")
        """
        if limit <= 0:
            logger.warning(f"patients_at_risk: limit inválido: {limit}")
            return []
        
        if not self.db.is_real or not self.db.client:
            return []
        
        try:
            response = (
                self.db.client.table("vw_pacientes_para_notificar")
                .select(
                    "perfil_id, nome_completo, "
                    "dias_sem_acesso, dias_sem_checkin, motivo"
                )
                .order("dias_sem_acesso", desc=True)
                .limit(limit)
                .execute()
            )
            
            patients = [RiskPatient.from_dict(p) for p in (response.data or [])]
            logger.info(f"✅ {len(patients)} pacientes em risco identificados")
            return patients
            
        except Exception as e:
            logger.warning(f"patients_at_risk falhou: {e}")
            return []

    def professional_actions(self) -> list[ProfessionalAction]:
        """
        Retorna lista de ações recomendadas ao profissional.
        
        Cada item responde: "O que devo fazer com este paciente agora?"
        
        Returns:
            Lista de objetos ProfessionalAction
            
        Example:
            >>> actions = notification_service.professional_actions()
            >>> for a in actions:
            ...     print(f"{a.icon} {a.patient_name}: {a.action}")
        """
        patients = self.patients_at_risk(limit=10)
        actions = []
        
        for p in patients:
            if p.is_critical:
                actions.append(ProfessionalAction(
                    patient_name=p.name,
                    patient_id=p.patient_id,
                    reason=f"🚨 {p.days_without_checkin} dias sem check-in",
                    action="Entrar em contato imediatamente",
                    urgency="alta",
                    icon="🚨",
                ))
            elif p.is_warning:
                actions.append(ProfessionalAction(
                    patient_name=p.name,
                    patient_id=p.patient_id,
                    reason=f"⚠️ {p.days_without_checkin} dias sem check-in",
                    action="Enviar mensagem de reforço",
                    urgency="media",
                    icon="⚠️",
                ))
            else:
                actions.append(ProfessionalAction(
                    patient_name=p.name,
                    patient_id=p.patient_id,
                    reason="📋 Acompanhamento regular",
                    action="Monitorar",
                    urgency="baixa",
                    icon="📋",
                ))
        
        logger.debug(f"✅ {len(actions)} ações profissionais geradas")
        return actions

    def clinical_summary(self) -> ClinicalSummary:
        """
        Retorna resumo clínico para gestores.
        
        Returns:
            Objeto ClinicalSummary com resumo agregado
            
        Example:
            >>> summary = notification_service.clinical_summary()
            >>> print(f"Total em risco: {summary.total}")
            >>> print(f"Recomendação: {summary.recommendation}")
        """
        patients = self.patients_at_risk(limit=100)
        
        if not patients:
            return ClinicalSummary(
                total=0,
                by_reason={},
                recommendation="✅ Todos os pacientes estão engajados.",
            )
        
        by_reason: dict[str, int] = {}
        for p in patients:
            by_reason[p.reason] = by_reason.get(p.reason, 0) + 1
        
        total = len(patients)
        
        if total >= 10:
            recommendation = "🚨 Alto número de pacientes em risco. Reforçar retenção."
        elif total >= 5:
            recommendation = "⚠️ Número moderado em risco. Revisar protocolos."
        else:
            recommendation = "✅ Nível de risco controlado. Manter estratégia."
        
        summary = ClinicalSummary(
            total=total,
            by_reason=by_reason,
            recommendation=recommendation,
        )
        
        logger.debug(f"✅ Resumo clínico: {total} pacientes em risco")
        return summary

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def _get_first_name(self, user: dict[str, Any] | Any) -> str:
        """
        Extrai primeiro nome do usuário.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Primeiro nome ou "Você"
        """
        if isinstance(user, dict):
            name = user.get("name", "")
        else:
            name = getattr(user, "name", "")
        
        if name:
            return name.split()[0]
        return "Você"


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER (APScheduler)
# ─────────────────────────────────────────────────────────────────────────────

def schedule_daily_reminders(db: Database) -> Any | None:
    """
    Inicia APScheduler em background.
    
    Agenda:
        - 20h: lembretes de refeição
        - 09h: avisos de trial expirando
    
    Args:
        db: Instância do Database
        
    Returns:
        Scheduler ou None se APScheduler não instalado
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler = BackgroundScheduler()
        
        # Lembrete diário às 20h
        scheduler.add_job(
            lambda: _run_daily_reminders(db),
            CronTrigger(hour=_DEFAULT_REMINDER_HOUR, minute=0),
            id="daily_reminders",
            replace_existing=True,
        )
        
        # Verificação de trial às 9h
        scheduler.add_job(
            lambda: _run_trial_check(db),
            CronTrigger(hour=_DEFAULT_TRIAL_HOUR, minute=0),
            id="trial_check",
            replace_existing=True,
        )

        # Alerta de streak em risco às 19h (antes do horário usual de check-in)
        scheduler.add_job(
            lambda: _run_streak_risk_alert(db),
            CronTrigger(hour=19, minute=0),
            id="streak_risk_alert",
            replace_existing=True,
        )

        scheduler.start()
        logger.info(f"✅ Agendador iniciado ({_DEFAULT_REMINDER_HOUR}h lembretes · {_DEFAULT_TRIAL_HOUR}h trial)")
        return scheduler
        
    except ImportError:
        logger.warning(
            "⚠️ APScheduler não instalado — notificações agendadas inativas. "
            "pip install apscheduler"
        )
    except Exception as e:
        logger.error(f"Agendador: {e}")
    
    return None


def _run_daily_reminders(db: Database) -> None:
    """Envia lembretes diários de refeição (20h)."""
    try:
        # Busca todos os usuários
        all_users = db.get_all_users() if hasattr(db, 'get_all_users') else []
        sent = 0
        
        for user_data in all_users:
            try:
                email = user_data.get("email", "")
                if not email:
                    continue
                
                if user_data.get("disable_reminders"):
                    continue
                
                # Verifica se tem refeições hoje
                today = date.today().isoformat()
                meals = db.get_meals_by_date(today)
                user_meals = [m for m in meals if (m.user_id if hasattr(m, 'user_id') else m.get("user_id")) == email]
                
                if user_meals:
                    continue
                
                # Calcula streak
                streak = _calculate_streak(db, email)
                name = user_data.get("name", "")
                
                if streak >= _STREAK_RISK_MIN:
                    send_streak_at_risk(email, name, streak)
                else:
                    send_meal_reminder(email, name, streak)
                
                sent += 1
                
            except Exception as e:
                logger.error(f"Lembrete {email}: {e}")
        
        logger.info(f"📧 Lembretes enviados: {sent}")
        
    except Exception as e:
        logger.error(f"_run_daily_reminders falhou: {e}")


def _run_trial_check(db: Database) -> None:
    """Verifica trials expirando (9h)."""
    try:
        # Busca todos os usuários
        all_users = db.get_all_users() if hasattr(db, 'get_all_users') else []
        
        for user_data in all_users:
            try:
                email = user_data.get("email", "")
                if not email:
                    continue
                
                plan = user_data.get("plan", "")
                if plan != "trial":
                    continue
                
                from core.models import User
                user = User.from_dict(user_data)
                days = user.trial_days_remaining()
                
                if days in (3, 1):
                    send_trial_expiring(email, user.name, days)
                    
            except Exception as e:
                logger.error(f"Trial {email}: {e}")
                
    except Exception as e:
        logger.error(f"_run_trial_check falhou: {e}")


def _run_streak_risk_alert(db: Database) -> None:
    """Alerta pacientes cujo streak está em risco (às 19h)."""
    try:
        all_users = db.get_all_users() if hasattr(db, "get_all_users") else []
        from datetime import date as _date
        hoje = _date.today().isoformat()
        
        for user_data in all_users:
            try:
                email = user_data.get("email", "")
                name = user_data.get("name", "")
                if not email or not name:
                    continue
                
                # Só alerta se preferência de email estiver ativa
                if user_data.get("notif_email_streak") is False:
                    continue

                # Já fez check-in hoje? Não precisa alertar
                checkin_hoje = None
                try:
                    checkins = db.client.table("checkins").select("data_checkin").eq("perfil_id", email).eq("data_checkin", hoje).limit(1).execute()
                    checkin_hoje = bool(checkins.data)
                except Exception:
                    pass

                if checkin_hoje:
                    continue

                streak = _calculate_streak(db, email)
                if streak >= 3:  # Só alerta se tem streak valioso para perder
                    send_streak_at_risk(email, name, streak)
                    logger.info(f"📧 Alerta streak enviado para {email} ({streak} dias)")

            except Exception as e:
                logger.error(f"Alerta streak {user_data.get('email', '?')}: {e}")

    except Exception as e:
        logger.error(f"_run_streak_risk_alert: {e}")


def _calculate_streak(db: Database, email: str) -> int:
    """Calcula streak de refeições para um usuário (fallback)."""
    try:
        today = date.today()
        streak = 0
        
        for i in range(1, 31):
            check_date = (today - timedelta(days=i)).isoformat()
            meals = db.get_meals_by_date(check_date)
            user_meals = [m for m in meals if (m.user_id if hasattr(m, 'user_id') else m.get("user_id")) == email]
            
            if user_meals:
                streak += 1
            else:
                break
        
        return streak
        
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# MANUAL
# ─────────────────────────────────────────────────────────────────────────────

def send_manual_reminder(email: str, name: str, db: Database) -> bool:
    """
    Envia lembrete manual para um paciente.
    
    Args:
        email: Email do paciente
        name: Nome do paciente
        db: Instância do Database
        
    Returns:
        True se enviado com sucesso
        
    Example:
        >>> from services.notification_service import send_manual_reminder
        >>> send_manual_reminder("patient@example.com", "João", db)
        True
    """
    try:
        streak = _calculate_streak(db, email)
        return send_meal_reminder(email, name, streak)
        
    except Exception as e:
        logger.error(f"send_manual_reminder falhou para {email}: {e}")
        return False


__all__ = [
    "NotificationService",
    "InAppNotification",
    "RiskPatient",
    "ProfessionalAction",
    "ClinicalSummary",
    "schedule_daily_reminders",
    "send_manual_reminder",
]
