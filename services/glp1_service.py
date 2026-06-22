"""
Melshape — GLP-1 Service.

Serviço para acompanhamento de pacientes em tratamento com GLP-1:
fases, adesão, sintomas, próximas doses e resumos.

Princípios:
- Fase: adaptação, manutenção, desmame ou parado
- Adesão: % de doses registradas vs esperadas
- Sintomas: monitoramento de efeitos colaterais
- Próxima dose: estimativa baseada na frequência do medicamento
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    GLP1Service
    ├── Treatment Days
    │   └── treatment_days(user) -> int | None
    ├── Current Phase
    │   ├── current_phase(user) -> GLP1Phase
    │   └── get_all_phases() -> list[GLP1Phase]
    ├── Adherence
    │   └── weekly_adherence(medication) -> GLP1Adherence
    ├── Next Dose
    │   └── next_dose(medication) -> str | None
    ├── Alerts
    │   └── symptom_alerts() -> list[str]
    ├── Summary
    │   └── summary(user) -> GLP1Summary
    ├── Statistics
    │   └── get_glp1_stats(user) -> GLP1Stats
    └── Utilities
        ├── get_medication_info(medication) -> MedicationInfo | None
        ├── get_symptom_label(code) -> str
        └── is_on_treatment(user) -> bool
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import config
from core.database import Database
from core.models import SEVERE_SYMPTOMS, SYMPTOM_LIST

logger = logging.getLogger("Melshape.GLP1Service")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Frequência esperada por tipo (doses/semana)
_WEEKLY_FREQUENCY: dict[str, int] = {
    "Ozempic (Semaglutida)": 1,
    "Wegovy (Semaglutida)": 1,
    "Mounjaro (Tirzepatida)": 1,
    "Zepbound (Tirzepatida)": 1,
    "Victoza (Liraglutida)": 7,   # Diário
    "Saxenda (Liraglutida)": 7,   # Diário
    "Outro": 1,
}

# Dias para cálculos
_ADHERENCE_DAYS: int = 28  # 4 semanas
_SYMPTOMS_DAYS: int = 3  # Últimos 3 dias
_DOSES_DAYS: int = 90
_DOSES_LIMIT: int = 30
_TREATMENT_DAYS: int = 28
_LAST_DOSE_DAYS: int = 365

# Thresholds
_ADHERENCE_GOOD_THRESHOLD: int = 80
_ADHERENCE_MODERATE_THRESHOLD: int = 50
_ADHERENT_DAYS_THRESHOLD: int = 7

# Labels dos sintomas graves
_SEVERE_SYMPTOM_LABELS: dict[str, str] = {
    "nausea": "Náusea intensa",
    "dizziness": "Tontura",
    "pain": "Dor abdominal",
    "vomiting": "Vômito",
}

# Fases do tratamento GLP-1
_PHASES: dict[str, dict[str, str]] = {
    "adapting": {
        "key": "adapting",
        "icon": "🔬",
        "label": "Adaptação",
        "color": "var(--info)",
        "description": "Primeiras semanas — monitorar sintomas",
    },
    "maintenance": {
        "key": "maintenance",
        "icon": "✅",
        "label": "Manutenção",
        "color": "var(--success)",
        "description": "Dose estabilizada — foco em hábitos",
    },
    "tapering": {
        "key": "tapering",
        "icon": "📉",
        "label": "Desmame",
        "color": "var(--warning)",
        "description": "Redução gradual — manter hábitos",
    },
    "stopped": {
        "key": "stopped",
        "icon": "⏹️",
        "label": "Parado",
        "color": "var(--error)",
        "description": "Tratamento encerrado",
    },
}

_VALID_PHASES: set[str] = {"adapting", "maintenance", "tapering", "stopped"}


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO GLP-1
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GLP1Phase:
    """
    Modelo de fase do tratamento GLP-1.
    
    Attributes:
        key: Chave da fase (adapting/maintenance/tapering/stopped)
        icon: Ícone representativo
        label: Nome da fase
        color: Cor para exibição (CSS)
        description: Descrição da fase
    """
    key: str
    icon: str
    label: str
    color: str
    description: str
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GLP1Phase:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            key=data.get("key", "adapting"),
            icon=data.get("icon", "🔬"),
            label=data.get("label", "Adaptação"),
            color=data.get("color", "var(--info)"),
            description=data.get("description", "Primeiras semanas — monitorar sintomas"),
        )
    
    @property
    def emoji(self) -> str:
        """Alias para icon."""
        return self.icon
    
    @property
    def is_active(self) -> bool:
        """Verifica se a fase é ativa (não parada)."""
        return self.key != "stopped"
    
    @property
    def is_adapting(self) -> bool:
        """Verifica se está em fase de adaptação."""
        return self.key == "adapting"
    
    @property
    def is_maintenance(self) -> bool:
        """Verifica se está em fase de manutenção."""
        return self.key == "maintenance"
    
    @property
    def is_tapering(self) -> bool:
        """Verifica se está em fase de desmame."""
        return self.key == "tapering"


@dataclass(frozen=True)
class GLP1Adherence:
    """
    Modelo de adesão ao tratamento GLP-1.
    
    Attributes:
        registered: Doses registradas no período
        expected: Doses esperadas no período
        percentage: Percentual de adesão (0-100)
        per_week: Frequência esperada por semana
        period_days: Período de cálculo em dias
    """
    registered: int
    expected: int
    percentage: int
    per_week: int
    period_days: int = _ADHERENCE_DAYS
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GLP1Adherence:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            registered=int(data.get("registered", 0)),
            expected=int(data.get("expected", 0)),
            percentage=int(data.get("percentage", 0)),
            per_week=int(data.get("per_week", 1)),
            period_days=int(data.get("period_days", _ADHERENCE_DAYS)),
        )
    
    @property
    def is_good(self) -> bool:
        """Verifica se a adesão é boa (>= 80%)."""
        return self.percentage >= _ADHERENCE_GOOD_THRESHOLD
    
    @property
    def is_moderate(self) -> bool:
        """Verifica se a adesão é moderada (50-79%)."""
        return _ADHERENCE_MODERATE_THRESHOLD <= self.percentage < _ADHERENCE_GOOD_THRESHOLD
    
    @property
    def is_poor(self) -> bool:
        """Verifica se a adesão é baixa (< 50%)."""
        return self.percentage < _ADHERENCE_MODERATE_THRESHOLD
    
    @property
    def status_label(self) -> str:
        """Retorna rótulo do status de adesão."""
        if self.is_good:
            return "✅ Boa"
        elif self.is_moderate:
            return "⚠️ Moderada"
        return "🔴 Baixa"
    
    @property
    def status_icon(self) -> str:
        """Retorna ícone do status de adesão."""
        if self.is_good:
            return "✅"
        elif self.is_moderate:
            return "⚠️"
        return "🔴"
    
    @property
    def missed_doses(self) -> int:
        """Calcula doses perdidas no período."""
        return max(0, self.expected - self.registered)


@dataclass(frozen=True)
class GLP1Summary:
    """
    Modelo de resumo do tratamento GLP-1.
    
    Attributes:
        medication: Medicamento em uso
        current_dose: Dose atual
        phase: Fase atual do tratamento
        days: Dias de tratamento
        next_dose: Data da próxima dose
        adherence: Adesão ao tratamento
        medication_class: Classe do medicamento (GLP-1/GIP)
    """
    medication: str
    current_dose: str
    phase: GLP1Phase
    days: int | None
    next_dose: str | None
    adherence: GLP1Adherence
    medication_class: str = "GLP-1"
    
    @property
    def is_on_treatment(self) -> bool:
        """Verifica se o paciente está em tratamento ativo."""
        return self.phase.is_active
    
    @property
    def treatment_duration_label(self) -> str:
        """Retorna label da duração do tratamento."""
        if self.days is None:
            return "Não informado"
        if self.days < 7:
            return f"{self.days} dias"
        elif self.days < 30:
            weeks = self.days // 7
            return f"{weeks} semana{'s' if weeks > 1 else ''}"
        else:
            months = self.days // 30
            return f"{months} mês{'es' if months > 1 else ''}"
    
    @property
    def adherence_status(self) -> str:
        """Retorna status de adesão para exibição."""
        return self.adherence.status_label
    
    @property
    def has_medication(self) -> bool:
        """Verifica se há medicamento registrado."""
        return bool(self.medication and self.medication.strip())


@dataclass(frozen=True)
class GLP1Stats:
    """
    Estatísticas do tratamento GLP-1.
    
    Attributes:
        total_doses: Total de doses registradas
        average_interval: Intervalo médio entre doses (dias)
        last_dose_date: Data da última dose
        days_since_last_dose: Dias desde a última dose
        longest_streak: Maior sequência de doses semanais
        has_severe_symptoms: Se há sintomas graves recentes
        total_symptoms_registrations: Total de registros de sintomas
    """
    total_doses: int = 0
    average_interval: float = 0.0
    last_dose_date: str | None = None
    days_since_last_dose: int = 0
    longest_streak: int = 0
    has_severe_symptoms: bool = False
    total_symptoms_registrations: int = 0
    
    @property
    def is_adherent(self) -> bool:
        """Verifica se o paciente está aderente (< 7 dias sem dose)."""
        return self.days_since_last_dose < _ADHERENT_DAYS_THRESHOLD
    
    @property
    def needs_attention(self) -> bool:
        """Verifica se precisa de atenção (>= 7 dias sem dose)."""
        return self.days_since_last_dose >= _ADHERENT_DAYS_THRESHOLD
    
    @property
    def adherence_status(self) -> str:
        """Retorna status de adesão."""
        if self.is_adherent:
            return "✅ Aderente"
        return "⚠️ Atrasado"
    
    @property
    def has_recent_activity(self) -> bool:
        """Verifica se há atividade recente."""
        return self.total_doses > 0


@dataclass(frozen=True)
class MedicationInfo:
    """
    Informações sobre um medicamento GLP-1.
    
    Attributes:
        name: Nome do medicamento
        active_ingredient: Princípio ativo
        frequency_weekly: Frequência semanal (doses/semana)
        interval_days: Intervalo entre doses (dias)
        is_daily: Se é administração diária
        is_weekly: Se é administração semanal
    """
    name: str
    active_ingredient: str
    frequency_weekly: int
    interval_days: int
    is_daily: bool = False
    is_weekly: bool = True
    
    @classmethod
    def from_medication_name(cls, name: str) -> MedicationInfo | None:
        """Cria informações a partir do nome do medicamento."""
        medication_map = {
            "Ozempic (Semaglutida)": ("Semaglutida", 1, 7),
            "Wegovy (Semaglutida)": ("Semaglutida", 1, 7),
            "Mounjaro (Tirzepatida)": ("Tirzepatida", 1, 7),
            "Zepbound (Tirzepatida)": ("Tirzepatida", 1, 7),
            "Victoza (Liraglutida)": ("Liraglutida", 7, 1),
            "Saxenda (Liraglutida)": ("Liraglutida", 7, 1),
        }
        
        if name not in medication_map:
            return None
        
        active, freq, interval = medication_map[name]
        
        return cls(
            name=name,
            active_ingredient=active,
            frequency_weekly=freq,
            interval_days=interval,
            is_daily=(freq == 7),
            is_weekly=(freq == 1),
        )


# ─────────────────────────────────────────────────────────────────────────────
# GLP-1 SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class GLP1Service:
    """
    Serviço de acompanhamento GLP-1.
    
    Gerencia fases, adesão, sintomas e próximas doses.
    
    Example:
        >>> db = Database()
        >>> glp1_service = GLP1Service(db)
        >>> user = st.session_state.user
        >>> summary = glp1_service.summary(user)
        >>> print(f"Fase: {summary.phase.label}")
        >>> print(f"Adesão: {summary.adherence.percentage}%")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço GLP-1.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ GLP1Service inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # TREATMENT DAYS
    # ─────────────────────────────────────────────────────────────────────────

    def treatment_days(self, user: dict[str, Any] | Any) -> int | None:
        """
        Calcula dias de tratamento GLP-1.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Número de dias de tratamento ou None se não houver início
            
        Example:
            >>> days = glp1_service.treatment_days(user)
            >>> if days:
            ...     print(f"{days} dias de tratamento")
        """
        if not user:
            logger.warning("treatment_days: user não informado")
            return None
        
        # Extrai data de início
        start_date = self._get_start_date(user)
        
        if not start_date:
            logger.debug("treatment_days: sem data de início")
            return None
        
        try:
            start = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
            days = (date.today() - start).days
            result = max(0, days)
            logger.debug(f"✅ Dias de tratamento: {result}")
            return result
        except Exception as e:
            logger.warning(f"treatment_days falhou: {e}")
            return None

    def _get_start_date(self, user: dict[str, Any] | Any) -> str | None:
        """
        Extrai a data de início do tratamento.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Data de início em YYYY-MM-DD ou None
        """
        # Tenta do usuário
        if isinstance(user, dict):
            start = user.get("glp1_start_date")
        else:
            start = getattr(user, "glp1_start_date", None)
        
        if start:
            return start
        
        # Tenta do protocolo ativo
        protocol = self.db.get_active_protocol()
        if protocol:
            iniciado_em = protocol.iniciado_em if hasattr(protocol, "iniciado_em") else protocol.get("iniciado_em")
            if iniciado_em:
                return iniciado_em
        
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # CURRENT PHASE
    # ─────────────────────────────────────────────────────────────────────────

    def current_phase(self, user: dict[str, Any] | Any) -> GLP1Phase:
        """
        Retorna a fase atual do tratamento.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto GLP1Phase com dados da fase
            
        Example:
            >>> phase = glp1_service.current_phase(user)
            >>> print(f"{phase.icon} {phase.label}: {phase.description}")
        """
        # Extrai fase do usuário ou protocolo
        phase_key = self._get_phase_key(user)
        
        # Busca dados da fase
        phase_data = _PHASES.get(phase_key, _PHASES["adapting"])
        phase = GLP1Phase.from_dict(phase_data)
        
        logger.debug(f"✅ Fase atual: {phase.label} ({phase_key})")
        return phase

    def _get_phase_key(self, user: dict[str, Any] | Any) -> str:
        """
        Extrai a chave da fase.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Chave da fase
        """
        # Tenta do usuário
        if isinstance(user, dict):
            phase = user.get("glp1_phase")
        else:
            phase = getattr(user, "glp1_phase", None)
        
        if phase and phase in _VALID_PHASES:
            return phase
        
        # Tenta do protocolo
        protocol = self.db.get_active_protocol()
        if protocol:
            fase = protocol.fase if hasattr(protocol, "fase") else protocol.get("fase")
            if fase in _VALID_PHASES:
                return fase
        
        # Fallback: adaptação
        return "adapting"

    def get_all_phases(self) -> list[GLP1Phase]:
        """
        Retorna todas as fases disponíveis.
        
        Returns:
            Lista de objetos GLP1Phase
            
        Example:
            >>> phases = glp1_service.get_all_phases()
            >>> for p in phases:
            ...     print(f"{p.icon} {p.label}")
        """
        return [GLP1Phase.from_dict(data) for data in _PHASES.values()]

    # ─────────────────────────────────────────────────────────────────────────
    # ADHERENCE
    # ─────────────────────────────────────────────────────────────────────────

    def weekly_adherence(self, medication: str) -> GLP1Adherence:
        """
        Calcula % de adesão nas últimas 4 semanas.
        
        Args:
            medication: Nome do medicamento
            
        Returns:
            Objeto GLP1Adherence com dados de adesão
            
        Example:
            >>> adherence = glp1_service.weekly_adherence("Ozempic")
            >>> print(f"Adesão: {adherence.percentage}%")
        """
        if not medication:
            logger.warning("weekly_adherence: medication não informado")
            return GLP1Adherence(registered=0, expected=0, percentage=0, per_week=1)
        
        expected_per_week = _WEEKLY_FREQUENCY.get(medication, 1)
        
        # Busca doses dos últimos 28 dias
        doses = self.db.get_doses(_ADHERENCE_DAYS)
        
        # Conta doses registradas
        registered = len(doses)
        expected_total = expected_per_week * 4
        
        # Calcula percentual
        if expected_total > 0:
            percentage = min(100, int(registered / expected_total * 100))
        else:
            percentage = 0
        
        adherence = GLP1Adherence(
            registered=registered,
            expected=expected_total,
            percentage=percentage,
            per_week=expected_per_week,
            period_days=_ADHERENCE_DAYS,
        )
        
        logger.debug(f"✅ Adesão: {adherence.percentage}% ({registered}/{expected_total})")
        return adherence

    # ─────────────────────────────────────────────────────────────────────────
    # NEXT DOSE
    # ─────────────────────────────────────────────────────────────────────────

    def next_dose(self, medication: str) -> str | None:
        """
        Estima data da próxima dose com base na última registrada.
        
        Args:
            medication: Nome do medicamento
            
        Returns:
            Descrição da próxima dose (ex: "Hoje", "Amanhã", "Em 3 dias")
            
        Example:
            >>> next_dose = glp1_service.next_dose("Ozempic")
            >>> print(f"Próxima dose: {next_dose}")
        """
        if not medication:
            logger.warning("next_dose: medication não informado")
            return None
        
        # Busca última dose
        last_dose = self.db.get_last_dose()
        
        if not last_dose:
            return "Hoje (primeira dose)"
        
        # Extrai data da última dose
        last_dose_date_str = self._get_dose_date(last_dose)
        
        if not last_dose_date_str:
            return None
        
        try:
            # Calcula frequência
            freq = _WEEKLY_FREQUENCY.get(medication, 1)
            interval = 7 // freq  # dias entre doses
            
            last_dose_date = datetime.strptime(last_dose_date_str, "%Y-%m-%d").date()
            next_dose_date = last_dose_date + timedelta(days=interval)
            delta = (next_dose_date - date.today()).days
            
            if delta <= 0:
                return "Hoje"
            elif delta == 1:
                return "Amanhã"
            elif delta <= 7:
                return f"Em {delta} dias ({next_dose_date.strftime('%d/%m')})"
            else:
                return f"{next_dose_date.strftime('%d/%m/%Y')} ({delta} dias)"
            
        except Exception as e:
            logger.warning(f"next_dose falhou: {e}")
            return None

    def _get_dose_date(self, dose: Any) -> str | None:
        """
        Extrai a data de uma dose.
        
        Args:
            dose: Objeto ou dicionário da dose
            
        Returns:
            Data em YYYY-MM-DD ou None
        """
        if hasattr(dose, "data_aplicacao"):
            return dose.data_aplicacao
        if isinstance(dose, dict):
            return dose.get("data_aplicacao")
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # SYMPTOM ALERTS
    # ─────────────────────────────────────────────────────────────────────────

    def symptom_alerts(self) -> list[str]:
        """
        Verifica sintomas graves nos últimos 3 dias.
        
        Returns:
            Lista de alertas médicos
            
        Example:
            >>> alerts = glp1_service.symptom_alerts()
            >>> for alert in alerts:
            ...     print(f"⚠️ {alert}")
        """
        alerts = []
        
        try:
            # Busca sintomas dos últimos 3 dias
            symptoms = self.db.get_symptoms(_SYMPTOMS_DAYS)
            
            if not symptoms:
                return alerts
            
            # Coleta sintomas graves
            recent_severe = set()
            
            for s in symptoms:
                symptom_list = self._extract_symptoms(s)
                recent_severe.update(
                    cod for cod in symptom_list if cod in SEVERE_SYMPTOMS
                )
            
            # Gera alertas
            for cod in recent_severe:
                label = _SEVERE_SYMPTOM_LABELS.get(cod, cod)
                alerts.append(
                    f"⚠️ {label} reportada nos últimos 3 dias. "
                    f"Considere consultar seu médico."
                )
            
            # Alerta calórico
            self._add_calorie_alert(alerts)
            
            if alerts:
                logger.info(f"✅ {len(alerts)} alertas de sintomas gerados")
            
            return alerts
            
        except Exception as e:
            logger.error(f"symptom_alerts falhou: {e}")
            return []

    def _extract_symptoms(self, symptom_data: Any) -> list[str]:
        """
        Extrai lista de sintomas de um objeto ou dicionário.
        
        Args:
            symptom_data: Objeto ou dicionário de sintoma
            
        Returns:
            Lista de códigos de sintomas
        """
        if hasattr(symptom_data, "sintomas"):
            symptoms = symptom_data.sintomas
        else:
            symptoms = symptom_data.get("sintomas", [])
        
        if isinstance(symptoms, str):
            try:
                return json.loads(symptoms)
            except json.JSONDecodeError:
                return []
        
        return symptoms if isinstance(symptoms, list) else []

    def _add_calorie_alert(self, alerts: list[str]) -> None:
        """
        Adiciona alerta calórico se aplicável.
        
        Args:
            alerts: Lista para adicionar o alerta
        """
        try:
            from services.nutrition_alerts import glp1_low_calorie_alert
            from services.nutrition_service import NutritionService
            
            nutrition = NutritionService(self.db)
            calorie_alert = glp1_low_calorie_alert(nutrition.daily_summary)
            
            if calorie_alert:
                alerts.append(calorie_alert)
        except Exception as e:
            logger.debug(f"_add_calorie_alert falhou: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────────

    def summary(self, user: dict[str, Any] | Any) -> GLP1Summary:
        """
        Retorna resumo completo do tratamento GLP-1.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto GLP1Summary com resumo completo
            
        Example:
            >>> summary = glp1_service.summary(user)
            >>> print(f"Medicamento: {summary.medication}")
            >>> print(f"Fase: {summary.phase.label}")
            >>> print(f"Adesão: {summary.adherence.percentage}%")
        """
        # Extrai dados do usuário
        medication, dose = self._get_medication_and_dose(user)
        
        # Fase atual
        phase = self.current_phase(user)
        
        # Dias de tratamento
        days = self.treatment_days(user)
        
        # Próxima dose
        next_dose_text = self.next_dose(medication)
        
        # Adesão
        adherence = self.weekly_adherence(medication)
        
        # Classe do medicamento
        med_info = self.get_medication_info(medication)
        medication_class = med_info.active_ingredient if med_info else "GLP-1"
        
        summary = GLP1Summary(
            medication=medication,
            current_dose=dose,
            phase=phase,
            days=days,
            next_dose=next_dose_text,
            adherence=adherence,
            medication_class=medication_class,
        )
        
        logger.debug(f"✅ Resumo GLP-1: {medication} - {phase.label}")
        return summary

    def _get_medication_and_dose(self, user: dict[str, Any] | Any) -> tuple[str, str]:
        """
        Extrai medicamento e dose do usuário ou protocolo.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Tupla (medicamento, dose)
        """
        # Tenta do usuário
        if isinstance(user, dict):
            medication = user.get("glp1_medication", "")
            dose = user.get("glp1_dose", "")
        else:
            medication = getattr(user, "glp1_medication", "")
            dose = getattr(user, "glp1_dose", "")
        
        # Tenta do protocolo ativo
        protocol = self.db.get_active_protocol()
        if protocol:
            if hasattr(protocol, "medicamento"):
                medication = protocol.medicamento or medication
            else:
                medication = protocol.get("medicamento", medication)
            
            if hasattr(protocol, "dose_atual"):
                dose = protocol.dose_atual or dose
            else:
                dose = protocol.get("dose_atual", dose)
        
        return medication, dose

    # ─────────────────────────────────────────────────────────────────────────
    # STATISTICS
    # ─────────────────────────────────────────────────────────────────────────

    def get_glp1_stats(self, user: dict[str, Any] | Any) -> GLP1Stats:
        """
        Retorna estatísticas detalhadas do tratamento GLP-1.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto GLP1Stats com estatísticas
            
        Example:
            >>> stats = glp1_service.get_glp1_stats(user)
            >>> print(f"Total de doses: {stats.total_doses}")
            >>> print(f"Dias desde última dose: {stats.days_since_last_dose}")
        """
        try:
            # Busca doses
            doses = self.db.get_doses(_DOSES_DAYS)
            
            total_doses = len(doses)
            
            # Última dose
            last_dose = self.db.get_last_dose()
            last_dose_date = self._get_dose_date(last_dose) if last_dose else None
            
            # Dias desde última dose
            if last_dose_date:
                try:
                    last_date = datetime.strptime(last_dose_date, "%Y-%m-%d").date()
                    days_since = (date.today() - last_date).days
                except Exception:
                    days_since = 0
            else:
                days_since = 0
            
            # Intervalo médio entre doses
            avg_interval = self._calculate_average_interval(doses)
            
            # Sintomas graves recentes
            has_severe = self._has_recent_severe_symptoms()
            
            # Total de registros de sintomas
            symptoms = self.db.get_symptoms(365)
            total_symptoms = len(symptoms)
            
            stats = GLP1Stats(
                total_doses=total_doses,
                average_interval=avg_interval,
                last_dose_date=last_dose_date,
                days_since_last_dose=days_since,
                longest_streak=0,  # TODO: implementar
                has_severe_symptoms=has_severe,
                total_symptoms_registrations=total_symptoms,
            )
            
            logger.debug(f"✅ Stats GLP-1: {total_doses} doses, {days_since}d desde última")
            return stats
            
        except Exception as e:
            logger.error(f"get_glp1_stats falhou: {e}")
            return GLP1Stats()

    def _calculate_average_interval(self, doses: list) -> float:
        """
        Calcula intervalo médio entre doses.
        
        Args:
            doses: Lista de doses
            
        Returns:
            Intervalo médio em dias
        """
        if len(doses) < 2:
            return 0.0
        
        try:
            dates = []
            for d in doses:
                date_str = self._get_dose_date(d)
                if date_str:
                    dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())
            
            if len(dates) < 2:
                return 0.0
            
            dates.sort(reverse=True)
            
            intervals = []
            for i in range(len(dates) - 1):
                diff = (dates[i] - dates[i + 1]).days
                if diff > 0:
                    intervals.append(diff)
            
            if not intervals:
                return 0.0
            
            return round(sum(intervals) / len(intervals), 1)
            
        except Exception as e:
            logger.debug(f"_calculate_average_interval falhou: {e}")
            return 0.0

    def _has_recent_severe_symptoms(self) -> bool:
        """
        Verifica se há sintomas graves nos últimos 3 dias.
        
        Returns:
            True se houver sintomas graves
        """
        try:
            symptoms = self.db.get_symptoms(_SYMPTOMS_DAYS)
            
            for s in symptoms:
                symptom_list = self._extract_symptoms(s)
                for cod in symptom_list:
                    if cod in SEVERE_SYMPTOMS:
                        return True
            
            return False
            
        except Exception as e:
            logger.debug(f"_has_recent_severe_symptoms falhou: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def get_medication_info(self, medication: str) -> MedicationInfo | None:
        """
        Retorna informações sobre um medicamento GLP-1.
        
        Args:
            medication: Nome do medicamento
            
        Returns:
            Objeto MedicationInfo ou None se não encontrado
            
        Example:
            >>> info = glp1_service.get_medication_info("Ozempic (Semaglutida)")
            >>> if info:
            ...     print(f"Princípio ativo: {info.active_ingredient}")
            ...     print(f"Frequência: {info.frequency_weekly}x por semana")
        """
        if not medication:
            return None
        
        return MedicationInfo.from_medication_name(medication)

    def get_symptom_label(self, code: str) -> str:
        """
        Retorna o label de um sintoma pelo código.
        
        Args:
            code: Código do sintoma
            
        Returns:
            Label do sintoma
            
        Example:
            >>> label = glp1_service.get_symptom_label("nausea")
            >>> print(label)  # "Náusea"
        """
        for cod, label in SYMPTOM_LIST:
            if cod == code:
                return label
        return code

    def is_on_treatment(self, user: dict[str, Any] | Any) -> bool:
        """
        Verifica se o paciente está em tratamento ativo.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            True se estiver em tratamento ativo
            
        Example:
            >>> if glp1_service.is_on_treatment(user):
            ...     print("Paciente em tratamento ativo")
        """
        phase = self.current_phase(user)
        return phase.is_active

    def get_treatment_duration_label(self, user: dict[str, Any] | Any) -> str:
        """
        Retorna label da duração do tratamento.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Label da duração (ex: "2 semanas", "3 meses")
            
        Example:
            >>> label = glp1_service.get_treatment_duration_label(user)
            >>> print(label)  # "2 semanas"
        """
        days = self.treatment_days(user)
        
        if days is None:
            return "Não informado"
        if days < 7:
            return f"{days} dias"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} semana{'s' if weeks > 1 else ''}"
        else:
            months = days // 30
            return f"{months} mês{'es' if months > 1 else ''}"

    # ─────────────────────────────────────────────────────────────────────────
    # ALIASES (COMPATIBILIDADE)
    # ─────────────────────────────────────────────────────────────────────────

    def dias_tratamento(self, user: dict[str, Any] | Any) -> int | None:
        """Alias para treatment_days (compatibilidade)."""
        return self.treatment_days(user)

    def fase_atual(self, user: dict[str, Any] | Any) -> GLP1Phase:
        """Alias para current_phase (compatibilidade)."""
        return self.current_phase(user)

    def adesao_semanal(self, medication: str) -> GLP1Adherence:
        """Alias para weekly_adherence (compatibilidade)."""
        return self.weekly_adherence(medication)

    def proxima_dose(self, medication: str) -> str | None:
        """Alias para next_dose (compatibilidade)."""
        return self.next_dose(medication)

    def alertas_sintomas(self) -> list[str]:
        """Alias para symptom_alerts (compatibilidade)."""
        return self.symptom_alerts()

    def resumo(self, user: dict[str, Any] | Any) -> GLP1Summary:
        """Alias para summary (compatibilidade)."""
        return self.summary(user)

    def get_phase_phases(self) -> list[GLP1Phase]:
        """Alias para get_all_phases (compatibilidade)."""
        return self.get_all_phases()


__all__ = [
    "GLP1Service",
    "GLP1Phase",
    "GLP1Adherence",
    "GLP1Summary",
    "GLP1Stats",
    "MedicationInfo",
]
