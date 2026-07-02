"""
Melshape — GLP-1 Repository.

Gerencia o acompanhamento de pacientes em tratamento com GLP-1:
doses, sintomas e protocolos.

Princípios:
- Dose: registro de cada aplicação do medicamento
- Sintomas: registro diário de sintomas e severidade
- Protocolo: plano de tratamento ativo do paciente
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Modelos: dataclasses imutáveis para todas as entidades
- Validação: dados são validados antes de salvar
- Logging: todas as operações são logadas

Arquitetura:
    GLP1Repository
    ├── register_dose(medicamento, dose, fase, observacao, protocolo_id) -> bool
    ├── get_doses(days) -> list[GLP1Dose]
    ├── get_last_dose() -> GLP1Dose | None
    ├── days_since_last_dose() -> int
    ├── register_symptoms(sintomas, severidade, observacao) -> bool
    ├── get_symptoms(days) -> list[GLP1Symptom]
    ├── get_active_protocol() -> GLP1Protocol | None
    ├── create_protocol(medicamento, dose_inicial) -> GLP1Protocol | None
    ├── update_protocol_dose(nova_dose) -> bool
    ├── update_protocol_phase(nova_fase) -> bool
    └── deactivate_protocol() -> bool
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import config

logger = logging.getLogger("Melshape.GLP1Repo")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS GLP-1
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GLP1Dose:
    """
    Modelo de dose de GLP-1 registrada.
    
    Attributes:
        id: ID único do registro
        user_id: ID do usuário
        medicamento: Nome do medicamento
        dose: Dose aplicada
        fase: Fase do tratamento (adapting/maintenance/tapering/stopped)
        data_aplicacao: Data da aplicação (YYYY-MM-DD)
        observacao: Observação opcional
        protocolo_id: ID do protocolo ativo
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    medicamento: str
    dose: str
    fase: str
    data_aplicacao: str = field(default_factory=lambda: date.today().isoformat())
    observacao: str = ""
    protocolo_id: str = ""
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GLP1Dose:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            medicamento=data.get("medicamento", ""),
            dose=data.get("dose", ""),
            fase=data.get("fase", "adapting"),
            data_aplicacao=data.get("data_aplicacao", date.today().isoformat()),
            observacao=data.get("observacao", ""),
            protocolo_id=data.get("protocolo_id", ""),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )


@dataclass(frozen=True)
class GLP1Symptom:
    """
    Modelo de registro de sintomas GLP-1.
    
    Attributes:
        id: ID único do registro
        user_id: ID do usuário
        sintomas: Lista de códigos de sintomas
        severidade: Severidade geral (1-3)
        data_registro: Data do registro (YYYY-MM-DD)
        observacao: Observação opcional
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    sintomas: list[str]
    severidade: int
    data_registro: str = field(default_factory=lambda: date.today().isoformat())
    observacao: str = ""
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GLP1Symptom:
        """Cria uma instância a partir de um dicionário."""
        # Converte sintomas de JSON string para list (se necessário)
        sintomas_raw = data.get("sintomas", [])
        if isinstance(sintomas_raw, str):
            try:
                sintomas = json.loads(sintomas_raw)
            except json.JSONDecodeError:
                sintomas = []
        else:
            sintomas = sintomas_raw
        
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            sintomas=sintomas,
            severidade=int(data.get("severidade", 1)),
            data_registro=data.get("data_registro", date.today().isoformat()),
            observacao=data.get("observacao", ""),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def has_severe_symptoms(self) -> bool:
        """Verifica se há sintomas graves."""
        return any(s in config.SEVERE_SYMPTOMS for s in self.sintomas)
    
    @property
    def severity_label(self) -> str:
        """Retorna o rótulo da severidade."""
        labels = {1: "Leve", 2: "Moderada", 3: "Grave"}
        return labels.get(self.severidade, str(self.severidade))


@dataclass(frozen=True)
class GLP1Protocol:
    """
    Modelo de protocolo de tratamento GLP-1.
    
    Attributes:
        id: ID único do protocolo
        user_id: ID do usuário
        medicamento: Nome do medicamento
        dose_inicial: Dose inicial
        dose_atual: Dose atual
        fase: Fase do tratamento (adapting/maintenance/tapering/stopped)
        ativo: Se o protocolo está ativo
        iniciado_em: Data de início
        finalizado_em: Data de finalização (se aplicável)
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    medicamento: str
    dose_inicial: str
    dose_atual: str
    fase: str = "adapting"
    ativo: bool = True
    iniciado_em: str = field(default_factory=lambda: date.today().isoformat())
    finalizado_em: str | None = None
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GLP1Protocol:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            medicamento=data.get("medicamento", ""),
            dose_inicial=data.get("dose_inicial", ""),
            dose_atual=data.get("dose_atual", data.get("dose_inicial", "")),
            fase=data.get("fase", "adapting"),
            ativo=data.get("ativo", True),
            iniciado_em=data.get("iniciado_em", date.today().isoformat()),
            finalizado_em=data.get("finalizado_em"),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def phase_label(self) -> str:
        """Retorna o rótulo da fase."""
        return config.GLP1_PHASES.get(self.fase, self.fase)
    
    @property
    def is_active(self) -> bool:
        """Verifica se o protocolo está ativo."""
        return self.ativo and self.fase != "stopped"


# ─────────────────────────────────────────────────────────────────────────────
# GLP-1 REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────

class GLP1Repository:
    """
    Mixin para gerenciamento GLP-1.
    
    Requer que a classe base tenha:
        - self.client (Supabase client)
        - self.is_real (bool)
        - self.uid() -> str
        - self.mock (dict)
    
    Example:
        >>> class Database(GLP1Repository):
        ...     def __init__(self):
        ...         self.client = None
        ...         self.is_real = False
        ...         self.mock = {"doses_glp1": []}
        ...     
        ...     def uid(self) -> str:
        ...         return "user@example.com"
        
        >>> db = Database()
        >>> db.register_dose("Ozempic", "0.5mg", "adapting")
        True
    """

    # ─────────────────────────────────────────────────────────────────────────
    # DOSES
    # ─────────────────────────────────────────────────────────────────────────

    def register_dose(
        self,
        medicamento: str,
        dose: str,
        fase: str,
        observacao: str = "",
        protocolo_id: str = "",
    ) -> bool:
        """
        Registra uma aplicação de GLP-1.
        
        Args:
            medicamento: Nome do medicamento
            dose: Dose aplicada
            fase: Fase do tratamento (adapting/maintenance/tapering/stopped)
            observacao: Observação opcional
            protocolo_id: ID do protocolo ativo
            
        Returns:
            True se registrado com sucesso, False caso contrário
            
        Example:
            >>> success = db.register_dose("Ozempic", "0.5mg", "adapting")
            >>> if success:
            ...     print("Dose registrada!")
        """
        uid = self.uid()
        
        # Validações
        if not medicamento or not medicamento.strip():
            logger.warning("❌ Medicamento é obrigatório")
            return False
        
        if not dose or not dose.strip():
            logger.warning("❌ Dose é obrigatória")
            return False
        
        valid_fases = {"adapting", "maintenance", "tapering", "stopped"}
        if fase not in valid_fases:
            logger.warning(f"❌ Fase inválida: {fase}")
            return False
        
        # Verifica se o medicamento é válido
        valid_medications = [m.lower() for m in config.GLP1_MEDICATIONS]
        if medicamento.lower() not in valid_medications and medicamento.lower() != "outro":
            logger.warning(f"❌ Medicamento não reconhecido: {medicamento}")
            # Permite continuar, mas loga warning
        
        dose_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                payload = {
                    "id": dose_id,
                    "perfil_id": uid,
                    "medicamento": medicamento,
                    "dose": dose,
                    "data_aplicacao": date.today().isoformat(),
                    "fase": fase,
                    "observacao": observacao or None,
                }
                if protocolo_id:
                    payload["protocolo_id"] = protocolo_id
                
                self.client.table("doses_glp1").insert(payload).execute()
                logger.info(f"✅ Dose registrada no Supabase: {medicamento} {dose}")
                return True
                
            except Exception as e:
                logger.error(f"register_dose Supabase: {e}")
        
        # Fallback MockDB
        self.mock.setdefault("doses_glp1", []).append({
            "id": dose_id,
            "user_id": uid,
            "medicamento": medicamento,
            "dose": dose,
            "fase": fase,
            "data_aplicacao": date.today().isoformat(),
            "observacao": observacao,
            "protocolo_id": protocolo_id,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        })
        
        logger.info(f"✅ Dose registrada no MockDB: {medicamento} {dose}")
        return True

    def get_doses(self, days: int = 90) -> list[GLP1Dose]:
        """
        Retorna as doses registradas nos últimos N dias.
        
        Args:
            days: Número de dias
            
        Returns:
            Lista de objetos GLP1Dose (ordenados por data descendente)
            
        Example:
            >>> doses = db.get_doses(days=30)
            >>> for dose in doses:
            ...     print(f"{dose.data_aplicacao}: {dose.medicamento} {dose.dose}")
        """
        uid = self.uid()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("doses_glp1")
                    .select("*")
                    .eq("perfil_id", uid)
                    .gte("data_aplicacao", cutoff)
                    .order("data_aplicacao", desc=True)
                    .execute()
                )
                
                return [self._build_dose_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_doses Supabase: {e}")
        
        # Fallback MockDB
        doses_data = [
            d for d in self.mock.get("doses_glp1", [])
            if d.get("user_id") == uid and d.get("data_aplicacao", "") >= cutoff
        ]
        
        # Ordena por data descendente
        sorted_doses = sorted(
            doses_data,
            key=lambda x: x.get("data_aplicacao", ""),
            reverse=True
        )
        
        return [self._build_dose_from_data(row) for row in sorted_doses]

    def get_last_dose(self) -> GLP1Dose | None:
        """
        Retorna a última dose registrada.
        
        Returns:
            Objeto GLP1Dose ou None
            
        Example:
            >>> last = db.get_last_dose()
            >>> if last:
            ...     print(f"Última dose: {last.medicamento} {last.dose} em {last.data_aplicacao}")
        """
        doses = self.get_doses(days=365)
        return doses[0] if doses else None

    def days_since_last_dose(self) -> int:
        """
        Calcula dias desde a última dose.
        
        Returns:
            Número de dias desde a última dose (0 se não houver registro)
            
        Example:
            >>> days = db.days_since_last_dose()
            >>> print(f"Dias desde última dose: {days}")
        """
        last_dose = self.get_last_dose()
        
        if not last_dose:
            return 0
        
        try:
            last_date = datetime.strptime(last_dose.data_aplicacao, "%Y-%m-%d").date()
            delta = (date.today() - last_date).days
            return max(0, delta)
        except Exception as e:
            logger.debug(f"days_since_last_dose: {e}")
            return 0

    # ─────────────────────────────────────────────────────────────────────────
    # SINTOMAS
    # ─────────────────────────────────────────────────────────────────────────

    def register_symptoms(
        self,
        sintomas: list[str],
        severidade: int,
        observacao: str = "",
    ) -> bool:
        """
        Registra sintomas do paciente.
        
        Args:
            sintomas: Lista de códigos de sintomas
            severidade: Severidade geral (1-3)
            observacao: Observação opcional
            
        Returns:
            True se registrado com sucesso, False caso contrário
            
        Example:
            >>> success = db.register_symptoms(["nausea", "fatigue"], 2)
            >>> if success:
            ...     print("Sintomas registrados!")
        """
        uid = self.uid()
        
        # Validações
        if not sintomas or not isinstance(sintomas, list):
            logger.warning("❌ sintomas deve ser uma lista não vazia")
            return False
        
        if not (1 <= severidade <= 3):
            logger.warning(f"❌ Severidade inválida: {severidade} (deve ser 1-3)")
            return False
        
        symptom_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                self.client.table("sintomas_glp1").insert({
                    "id": symptom_id,
                    "perfil_id": uid,
                    "data_registro": date.today().isoformat(),
                    "sintomas": json.dumps(sintomas),  # Converte para JSON no Supabase
                    "severidade": severidade,
                    "observacao": observacao or None,
                }).execute()
                
                logger.info(f"✅ Sintomas registrados no Supabase: {len(sintomas)} sintomas, severidade {severidade}")
                return True
                
            except Exception as e:
                logger.error(f"register_symptoms Supabase: {e}")
        
        # Fallback MockDB
        self.mock.setdefault("sintomas_glp1", []).append({
            "id": symptom_id,
            "user_id": uid,
            "sintomas": sintomas,  # Mantém como list no MockDB
            "severidade": severidade,
            "data_registro": date.today().isoformat(),
            "observacao": observacao,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        })
        
        logger.info(f"✅ Sintomas registrados no MockDB: {len(sintomas)} sintomas, severidade {severidade}")
        return True

    def get_symptoms(self, days: int = 30) -> list[GLP1Symptom]:
        """
        Retorna os sintomas registrados nos últimos N dias.
        
        Args:
            days: Número de dias
            
        Returns:
            Lista de objetos GLP1Symptom (ordenados por data descendente)
            
        Example:
            >>> symptoms = db.get_symptoms(days=7)
            >>> for s in symptoms:
            ...     print(f"{s.data_registro}: {s.sintomas} (severidade: {s.severidade})")
        """
        uid = self.uid()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("sintomas_glp1")
                    .select("*")
                    .eq("perfil_id", uid)
                    .gte("data_registro", cutoff)
                    .order("data_registro", desc=True)
                    .execute()
                )
                
                return [self._build_symptom_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_symptoms Supabase: {e}")
        
        # Fallback MockDB
        symptoms_data = [
            s for s in self.mock.get("sintomas_glp1", [])
            if s.get("user_id") == uid and s.get("data_registro", "") >= cutoff
        ]
        
        # Ordena por data descendente
        sorted_symptoms = sorted(
            symptoms_data,
            key=lambda x: x.get("data_registro", ""),
            reverse=True
        )
        
        return [self._build_symptom_from_data(row) for row in sorted_symptoms]

    # ─────────────────────────────────────────────────────────────────────────
    # PROTOCOLO
    # ─────────────────────────────────────────────────────────────────────────

    def get_active_protocol(self) -> GLP1Protocol | None:
        """
        Retorna o protocolo ativo do paciente.
        
        Returns:
            Objeto GLP1Protocol ou None
            
        Example:
            >>> protocol = db.get_active_protocol()
            >>> if protocol:
            ...     print(f"Protocolo: {protocol.medicamento} - {protocol.dose_atual}")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("protocolos_glp1")
                    .select("*")
                    .eq("perfil_id", uid)
                    .eq("ativo", True)
                    .limit(1)
                    .execute()
                )
                
                if response.data:
                    return self._build_protocol_from_data(response.data[0])
                
            except Exception as e:
                logger.error(f"get_active_protocol Supabase: {e}")
        
        # Fallback MockDB
        protocol_data = self.mock.get("protocolo_glp1")
        
        if protocol_data and protocol_data.get("user_id") == uid and protocol_data.get("ativo"):
            return self._build_protocol_from_data(protocol_data)
        
        return None

    def create_protocol(
        self,
        medicamento: str,
        dose_inicial: str,
    ) -> GLP1Protocol | None:
        """
        Cria um novo protocolo ativo para o paciente.
        
        Se já existe um protocolo ativo, ele é desativado automaticamente.
        
        Args:
            medicamento: Nome do medicamento
            dose_inicial: Dose inicial do protocolo
            
        Returns:
            Objeto GLP1Protocol criado ou None se falhar
            
        Example:
            >>> protocol = db.create_protocol("Ozempic", "0.25mg")
            >>> if protocol:
            ...     print(f"Protocolo criado: {protocol.id}")
        """
        uid = self.uid()
        
        # Validações
        if not medicamento or not medicamento.strip():
            logger.warning("❌ Medicamento é obrigatório")
            return None
        
        if not dose_inicial or not dose_inicial.strip():
            logger.warning("❌ Dose inicial é obrigatória")
            return None
        
        # Verifica se já existe protocolo ativo
        existing = self.get_active_protocol()
        if existing:
            logger.info(f"⚠️ Desativando protocolo anterior: {existing.id}")
            self.deactivate_protocol()
        
        protocol_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                response = self.client.table("protocolos_glp1").insert({
                    "id": protocol_id,
                    "perfil_id": uid,
                    "medicamento": medicamento,
                    "dose_inicial": dose_inicial,
                    "dose_atual": dose_inicial,
                    "fase": "adapting",
                    "ativo": True,
                    "iniciado_em": date.today().isoformat(),
                }).execute()
                
                if response.data:
                    protocol = self._build_protocol_from_data(response.data[0])
                    logger.info(f"✅ Protocolo criado no Supabase: {medicamento} {dose_inicial}")
                    return protocol
                
            except Exception as e:
                logger.error(f"create_protocol Supabase: {e}")
        
        # Fallback MockDB
        protocol_data = {
            "id": protocol_id,
            "user_id": uid,
            "medicamento": medicamento,
            "dose_inicial": dose_inicial,
            "dose_atual": dose_inicial,
            "fase": "adapting",
            "ativo": True,
            "iniciado_em": date.today().isoformat(),
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock["protocolo_glp1"] = protocol_data
        
        protocol = self._build_protocol_from_data(protocol_data)
        logger.info(f"✅ Protocolo criado no MockDB: {medicamento} {dose_inicial}")
        return protocol

    def update_protocol_dose(self, nova_dose: str) -> bool:
        """
        Atualiza a dose atual do protocolo ativo.
        
        Args:
            nova_dose: Nova dose do protocolo
            
        Returns:
            True se atualizado com sucesso, False caso contrário
            
        Example:
            >>> success = db.update_protocol_dose("0.5mg")
            >>> if success:
            ...     print("Dose atualizada!")
        """
        if not nova_dose or not nova_dose.strip():
            logger.warning("❌ Nova dose é obrigatória")
            return False
        
        protocol = self.get_active_protocol()
        
        if not protocol:
            logger.warning("❌ Nenhum protocolo ativo encontrado")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.table("protocolos_glp1").update({
                    "dose_atual": nova_dose,
                }).eq("id", protocol.id).execute()
                
                logger.info(f"✅ Dose atualizada no Supabase: {nova_dose}")
                return True
                
            except Exception as e:
                logger.error(f"update_protocol_dose Supabase: {e}")
        
        # Fallback MockDB
        protocol_data = self.mock.get("protocolo_glp1")
        if protocol_data:
            protocol_data["dose_atual"] = nova_dose
            logger.info(f"✅ Dose atualizada no MockDB: {nova_dose}")
            return True
        
        return False

    def update_protocol_phase(self, nova_fase: str) -> bool:
        """
        Atualiza a fase do protocolo ativo.
        
        Args:
            nova_fase: Nova fase (adapting/maintenance/tapering/stopped)
            
        Returns:
            True se atualizado com sucesso, False caso contrário
            
        Example:
            >>> success = db.update_protocol_phase("maintenance")
            >>> if success:
            ...     print("Fase atualizada!")
        """
        valid_fases = {"adapting", "maintenance", "tapering", "stopped"}
        
        if nova_fase not in valid_fases:
            logger.warning(f"❌ Fase inválida: {nova_fase}")
            return False
        
        protocol = self.get_active_protocol()
        
        if not protocol:
            logger.warning("❌ Nenhum protocolo ativo encontrado")
            return False
        
        if self.is_real and self.client:
            try:
                payload = {"fase": nova_fase}
                
                # Se fase é "stopped", desativa o protocolo
                if nova_fase == "stopped":
                    payload["ativo"] = False
                    payload["finalizado_em"] = date.today().isoformat()
                
                self.client.table("protocolos_glp1").update(payload).eq("id", protocol.id).execute()
                
                logger.info(f"✅ Fase atualizada no Supabase: {nova_fase}")
                return True
                
            except Exception as e:
                logger.error(f"update_protocol_phase Supabase: {e}")
        
        # Fallback MockDB
        protocol_data = self.mock.get("protocolo_glp1")
        if protocol_data:
            protocol_data["fase"] = nova_fase
            
            if nova_fase == "stopped":
                protocol_data["ativo"] = False
                protocol_data["finalizado_em"] = date.today().isoformat()
            
            logger.info(f"✅ Fase atualizada no MockDB: {nova_fase}")
            return True
        
        return False

    def deactivate_protocol(self) -> bool:
        """
        Desativa o protocolo ativo.
        
        Returns:
            True se desativado com sucesso, False caso contrário
            
        Example:
            >>> success = db.deactivate_protocol()
            >>> if success:
            ...     print("Protocolo desativado!")
        """
        protocol = self.get_active_protocol()
        
        if not protocol:
            logger.warning("❌ Nenhum protocolo ativo encontrado")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.table("protocolos_glp1").update({
                    "ativo": False,
                    "finalizado_em": date.today().isoformat(),
                }).eq("id", protocol.id).execute()
                
                logger.info(f"✅ Protocolo desativado no Supabase: {protocol.id}")
                return True
                
            except Exception as e:
                logger.error(f"deactivate_protocol Supabase: {e}")
        
        # Fallback MockDB
        protocol_data = self.mock.get("protocolo_glp1")
        if protocol_data:
            protocol_data["ativo"] = False
            protocol_data["finalizado_em"] = date.today().isoformat()
            logger.info(f"✅ Protocolo desativado no MockDB: {protocol.id}")
            return True
        
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE CONVERSÃO
    # ─────────────────────────────────────────────────────────────────────────

    def _build_dose_from_data(self, data: dict[str, Any]) -> GLP1Dose:
        """Converte um dicionário para um objeto GLP1Dose."""
        return GLP1Dose.from_dict(data)

    def _build_symptom_from_data(self, data: dict[str, Any]) -> GLP1Symptom:
        """Converte um dicionário para um objeto GLP1Symptom."""
        return GLP1Symptom.from_dict(data)

    def _build_protocol_from_data(self, data: dict[str, Any]) -> GLP1Protocol:
        """Converte um dicionário para um objeto GLP1Protocol."""
        return GLP1Protocol.from_dict(data)


__all__ = [
    "GLP1Repository",
    "GLP1Dose",
    "GLP1Symptom",
    "GLP1Protocol",
]
