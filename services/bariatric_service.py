"""
Melshape — Bariatric Service.

Serviço para acompanhamento de pacientes pós-cirurgia bariátrica:
fases automáticas, limites de volume/calorias, suplementação obrigatória,
progresso e alertas nutricionais.

Princípios:
- Fase automática: calculada por dias pós-cirurgia
- Limites: volume (ml) e calorias por fase
- Suplementação: lista de suplementos obrigatórios por fase
- Progresso: % de evolução rumo a 1 ano de acompanhamento
- Alertas: volume, calorias e proteína fora dos limites
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    BariatricService
    ├── Days Since Surgery
    │   └── days_since_surgery(user) -> int | None
    ├── Phase
    │   ├── automatic_phase(days) -> str
    │   ├── current_phase_data(phase_key) -> BariatricPhase
    │   ├── get_phase_by_days(days) -> BariatricPhase
    │   └── get_all_phases() -> list[BariatricPhase]
    ├── Progress
    │   ├── journey_progress(days) -> BariatricProgress
    │   └── get_weight_loss(user) -> float | None
    ├── Supplements
    │   └── phase_supplements(phase_key) -> list[BariatricSupplement]
    ├── Alerts
    │   └── alerts(phase_key, user) -> list[BariatricAlert]
    ├── Summary
    │   └── summary(user) -> BariatricSummary
    ├── Statistics
    │   └── get_bariatric_stats(user) -> BariatricStats
    └── Utilities
        ├── is_bariatric_user(user) -> bool
        └── get_weight_loss_percentage(user) -> float | None
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import config
from core.database import Database
from config import BARIATRIC_ESSENTIALS
from services.nutrition_service import NutritionService

logger = logging.getLogger("Melshape.BariatricService")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Dias de início e fim de cada fase
_PHASE_DAYS: dict[str, tuple[int, int]] = {
    "liquid": (0, 14),
    "pasty": (15, 30),
    "soft": (31, 60),
    "solid": (61, 180),
    "maintenance": (181, 99999),
}

# Ordem das fases (para progresso)
_PHASE_ORDER: list[str] = ["liquid", "pasty", "soft", "solid", "maintenance"]

# Suplementos por fase
_PHASE_SUPPLEMENTS: dict[str, list[str]] = {
    "liquid": ["Vitamina B1 (Tiamina)", "Vitamina D3", "Proteína Whey"],
    "pasty": ["Vitamina B12", "Vitamina D3", "Ferro", "Proteína Whey"],
    "soft": ["Vitamina B12", "Vitamina D3", "Ferro", "Cálcio Citrato", "Zinco", "Proteína Whey"],
    "solid": [e["name"] for e in BARIATRIC_ESSENTIALS],
    "maintenance": [e["name"] for e in BARIATRIC_ESSENTIALS],
}

# Meta de dias pós-cirurgia (usa config se disponível)
_TARGET_DAYS: int = getattr(config, "BARIATRIC_TARGET_DAYS", 365)

# Thresholds de alerta
_ALERT_VOLUME_PCT: float = 0.9  # 90% do volume máximo
_ALERT_CALORIE_PCT: float = 0.85  # 85% das calorias máximas
_PROTEIN_GOAL_PER_KG: float = 1.5  # g/kg para bariátricos
_PROTEIN_MIN_PCT: float = 0.6  # 60% da meta mínima para alerta
_PROTEIN_CRITICAL_PCT: float = 0.4  # 40% da meta para alerta crítico
_DAYS_UNTIL_PHASE_CHANGE: int = 3  # Dias para alerta de mudança de fase

# Descrições das fases
_PHASE_DESCRIPTIONS: dict[str, str] = {
    "liquid": "Alimentos líquidos — hidratação e volume controlado",
    "pasty": "Alimentos pastosos — introdução de texturas",
    "soft": "Alimentos brandos — mastigação controlada",
    "solid": "Alimentos sólidos — fracionamento e consistência",
    "maintenance": "Manutenção — hábitos permanentes",
}


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO BARIÁTRICO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BariatricPhase:
    """
    Modelo de fase pós-cirurgia bariátrica.
    
    Attributes:
        key: Chave da fase (liquid/pasty/soft/solid/maintenance)
        name: Nome da fase
        days_range: Intervalo de dias (ex: "0–14")
        max_ml: Volume máximo por refeição (ml)
        max_cal: Calorias máximas por dia (kcal)
        description: Descrição da fase
    """
    key: str
    name: str
    days_range: str
    max_ml: int
    max_cal: int
    description: str = ""
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BariatricPhase:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            key=data.get("key", ""),
            name=data.get("name", ""),
            days_range=data.get("days_range", ""),
            max_ml=int(data.get("max_ml", 0)),
            max_cal=int(data.get("max_cal", 0)),
            description=data.get("description", ""),
        )
    
    @property
    def is_liquid(self) -> bool:
        """Verifica se é fase líquida."""
        return self.key == "liquid"
    
    @property
    def is_pasty(self) -> bool:
        """Verifica se é fase pastosa."""
        return self.key == "pasty"
    
    @property
    def is_soft(self) -> bool:
        """Verifica se é fase branda."""
        return self.key == "soft"
    
    @property
    def is_solid(self) -> bool:
        """Verifica se é fase sólida."""
        return self.key == "solid"
    
    @property
    def is_maintenance(self) -> bool:
        """Verifica se é fase de manutenção."""
        return self.key == "maintenance"
    
    @property
    def phase_number(self) -> int:
        """Retorna o número da fase (1-5)."""
        try:
            return _PHASE_ORDER.index(self.key) + 1
        except ValueError:
            return 1
    
    @property
    def total_phases(self) -> int:
        """Retorna o total de fases."""
        return len(_PHASE_ORDER)
    
    @property
    def is_first_phase(self) -> bool:
        """Verifica se é a primeira fase."""
        return self.phase_number == 1
    
    @property
    def is_last_phase(self) -> bool:
        """Verifica se é a última fase."""
        return self.phase_number == self.total_phases
    
    @property
    def phase_progress_label(self) -> str:
        """Retorna label do progresso da fase."""
        return f"Fase {self.phase_number}/{self.total_phases}"
    
    @property
    def next_phase_key(self) -> str | None:
        """Retorna chave da próxima fase ou None se for a última."""
        if self.is_last_phase:
            return None
        return _PHASE_ORDER[self.phase_number]
    
    @property
    def max_cal_label(self) -> str:
        """Retorna label formatado das calorias máximas."""
        return f"{self.max_cal:,} kcal/dia"
    
    @property
    def max_ml_label(self) -> str:
        """Retorna label formatado do volume máximo."""
        return f"{self.max_ml} ml/refeição"


@dataclass(frozen=True)
class BariatricProgress:
    """
    Modelo de progresso da jornada bariátrica.
    
    Attributes:
        days: Dias pós-cirurgia
        target_days: Meta de dias (365)
        percentage: Percentual de progresso (0-100)
        remaining_days: Dias restantes para meta
        phase: Fase atual
    """
    days: int
    target_days: int
    percentage: int
    remaining_days: int
    phase: BariatricPhase
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BariatricProgress:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            days=int(data.get("days", 0)),
            target_days=int(data.get("target_days", _TARGET_DAYS)),
            percentage=int(data.get("percentage", 0)),
            remaining_days=int(data.get("remaining_days", 0)),
            phase=data.get("phase", BariatricPhase(
                key="liquid", name="Líquida", days_range="0–14", 
                max_ml=200, max_cal=600
            )),
        )
    
    @property
    def is_complete(self) -> bool:
        """Verifica se a jornada está completa."""
        return self.percentage >= 100
    
    @property
    def is_halfway(self) -> bool:
        """Verifica se atingiu metade do caminho."""
        return self.percentage >= 50
    
    @property
    def is_quarter(self) -> bool:
        """Verifica se atingiu 25% do caminho."""
        return self.percentage >= 25
    
    @property
    def is_three_quarters(self) -> bool:
        """Verifica se atingiu 75% do caminho."""
        return self.percentage >= 75
    
    @property
    def months_completed(self) -> int:
        """Retorna meses completos."""
        return self.days // 30
    
    @property
    def progress_label(self) -> str:
        """Retorna label do progresso."""
        if self.is_complete:
            return "🏆 Jornada Completa!"
        elif self.is_three_quarters:
            return f"🔥 {self.percentage}% — Quase lá!"
        elif self.is_halfway:
            return f"💪 {self.percentage}% — Metade do caminho!"
        elif self.is_quarter:
            return f"🌱 {self.percentage}% — Começando a jornada!"
        return f"🌱 {self.percentage}% — Primeiros passos"
    
    @property
    def progress_bar_text(self) -> str:
        """Retorna texto para barra de progresso."""
        return f"{self.percentage}% • {self.days}/{self.target_days} dias"
    
    @property
    def estimated_completion_date(self) -> date | None:
        """Estima data de conclusão da jornada."""
        if self.is_complete:
            return date.today()
        try:
            return date.today() + timedelta(days=self.remaining_days)
        except Exception:
            return None


@dataclass(frozen=True)
class BariatricSupplement:
    """
    Modelo de suplemento bariátrico.
    
    Attributes:
        name: Nome do suplemento
        dose: Dose recomendada
        unit: Unidade de medida
        phase: Fase em que é obrigatório
        is_essential: Se é suplemento essencial
    """
    name: str
    dose: str
    unit: str
    phase: str = ""
    is_essential: bool = True
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BariatricSupplement:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            name=data.get("name", ""),
            dose=data.get("dose", ""),
            unit=data.get("unit", ""),
            phase=data.get("phase", ""),
            is_essential=data.get("is_essential", True),
        )
    
    @property
    def display_dose(self) -> str:
        """Retorna dose formatada para exibição."""
        if not self.dose or not self.unit:
            return "—"
        return f"{self.dose} {self.unit}"
    
    @property
    def display_name(self) -> str:
        """Retorna nome com indicador de essencial."""
        if self.is_essential:
            return f"⭐ {self.name}"
        return self.name


@dataclass(frozen=True)
class BariatricAlert:
    """
    Modelo de alerta bariátrico.
    
    Attributes:
        type: Tipo do alerta (volume/calorie/protein/phase)
        severity: Severidade (info/warning/error)
        title: Título do alerta
        message: Mensagem do alerta
        action: Ação sugerida
    """
    type: str
    severity: str
    title: str
    message: str
    action: str = ""
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BariatricAlert:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            type=data.get("type", ""),
            severity=data.get("severity", "info"),
            title=data.get("title", ""),
            message=data.get("message", ""),
            action=data.get("action", ""),
        )
    
    @property
    def severity_icon(self) -> str:
        """Retorna ícone da severidade."""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨",
        }
        return icons.get(self.severity, "ℹ️")
    
    @property
    def severity_label(self) -> str:
        """Retorna label da severidade."""
        labels = {
            "info": "Informação",
            "warning": "Atenção",
            "error": "Urgente",
        }
        return labels.get(self.severity, "Informação")
    
    @property
    def is_warning(self) -> bool:
        """Verifica se é um alerta de atenção."""
        return self.severity == "warning"
    
    @property
    def is_error(self) -> bool:
        """Verifica se é um alerta urgente."""
        return self.severity == "error"
    
    @property
    def is_info(self) -> bool:
        """Verifica se é um alerta informativo."""
        return self.severity == "info"


@dataclass(frozen=True)
class BariatricSummary:
    """
    Modelo de resumo do acompanhamento bariátrico.
    
    Attributes:
        phase: Fase atual
        days: Dias pós-cirurgia
        surgery_type: Tipo de cirurgia
        progress: Progresso da jornada
        supplements: Lista de suplementos obrigatórios
        alerts: Lista de alertas ativos
        surgery_date: Data da cirurgia
        pre_surgery_weight: Peso pré-cirurgia
    """
    phase: BariatricPhase
    days: int | None
    surgery_type: str
    progress: BariatricProgress
    supplements: list[BariatricSupplement]
    alerts: list[BariatricAlert]
    surgery_date: str | None = None
    pre_surgery_weight: float | None = None
    
    @property
    def has_surgery(self) -> bool:
        """Verifica se há cirurgia registrada."""
        return self.surgery_date is not None
    
    @property
    def phase_label(self) -> str:
        """Retorna label da fase."""
        return f"{self.phase.phase_number}/{self.phase.total_phases} - {self.phase.name}"
    
    @property
    def days_label(self) -> str:
        """Retorna label dos dias."""
        if self.days is None:
            return "Não informado"
        return f"{self.days} dia{'s' if self.days != 1 else ''}"
    
    @property
    def has_alerts(self) -> bool:
        """Verifica se há alertas ativos."""
        return len(self.alerts) > 0
    
    @property
    def has_critical_alerts(self) -> bool:
        """Verifica se há alertas críticos (error)."""
        return any(a.is_error for a in self.alerts)
    
    @property
    def warning_alerts_count(self) -> int:
        """Retorna quantidade de alertas de atenção."""
        return sum(1 for a in self.alerts if a.is_warning)
    
    @property
    def info_alerts_count(self) -> int:
        """Retorna quantidade de alertas informativos."""
        return sum(1 for a in self.alerts if a.is_info)
    
    @property
    def supplements_count(self) -> int:
        """Retorna quantidade de suplementos obrigatórios."""
        return len(self.supplements)
    
    @property
    def is_in_liquid_phase(self) -> bool:
        """Verifica se está na fase líquida."""
        return self.phase.is_liquid
    
    @property
    def is_in_maintenance(self) -> bool:
        """Verifica se está na fase de manutenção."""
        return self.phase.is_maintenance


@dataclass(frozen=True)
class BariatricStats:
    """
    Estatísticas do acompanhamento bariátrico.
    
    Attributes:
        total_phase_changes: Total de mudanças de fase
        days_in_current_phase: Dias na fase atual
        average_volume_ml: Volume médio por refeição
        average_calories: Média de calorias diárias
        supplement_adherence: % de adesão à suplementação
        last_phase_change: Data da última mudança de fase
        weight_loss_kg: Perda de peso em kg
        weight_loss_percentage: Perda de peso em %
    """
    total_phase_changes: int = 0
    days_in_current_phase: int = 0
    average_volume_ml: float = 0.0
    average_calories: float = 0.0
    supplement_adherence: float = 0.0
    last_phase_change: str | None = None
    weight_loss_kg: float = 0.0
    weight_loss_percentage: float = 0.0
    
    @property
    def has_phase_changes(self) -> bool:
        """Verifica se houve mudanças de fase."""
        return self.total_phase_changes > 0
    
    @property
    def adherence_label(self) -> str:
        """Retorna label da adesão à suplementação."""
        if self.supplement_adherence >= 80:
            return "✅ Excelente"
        elif self.supplement_adherence >= 60:
            return "⚠️ Boa"
        elif self.supplement_adherence >= 40:
            return "⚡ Regular"
        return "🔴 Baixa"
    
    @property
    def weight_loss_label(self) -> str:
        """Retorna label da perda de peso."""
        if self.weight_loss_kg <= 0:
            return "—"
        return f"-{self.weight_loss_kg:.1f} kg ({self.weight_loss_percentage:.1f}%)"


# ─────────────────────────────────────────────────────────────────────────────
# BARIATRIC SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class BariatricService:
    """
    Serviço de acompanhamento bariátrico.
    
    Gerencia fases, limites, suplementação, progresso e alertas.
    
    Example:
        >>> db = Database()
        >>> bariatric_service = BariatricService(db)
        >>> user = st.session_state.user
        >>> summary = bariatric_service.summary(user)
        >>> print(f"Fase: {summary.phase.name}")
        >>> print(f"Progresso: {summary.progress.percentage}%")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço bariátrico.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        self._nutrition_service = NutritionService(db)
        logger.debug("✅ BariatricService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # DAYS SINCE SURGERY
    # ─────────────────────────────────────────────────────────────────────────

    def days_since_surgery(self, user: dict[str, Any] | Any) -> int | None:
        """
        Calcula dias desde a cirurgia.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Número de dias pós-cirurgia ou None se não houver data
            
        Example:
            >>> days = bariatric_service.days_since_surgery(user)
            >>> if days:
            ...     print(f"{days} dias pós-cirurgia")
        """
        if not user:
            logger.warning("days_since_surgery: user não informado")
            return None
        
        # Extrai data da cirurgia
        surgery_date = self._get_surgery_date(user)
        
        if not surgery_date:
            # Tenta buscar do banco
            surgery = self.db.get_surgery()
            if surgery:
                surgery_date = surgery.data_cirurgia if hasattr(surgery, "data_cirurgia") else surgery.get("data_cirurgia")
        
        if not surgery_date:
            logger.debug("days_since_surgery: sem data de cirurgia")
            return None
        
        try:
            surgery = datetime.strptime(surgery_date[:10], "%Y-%m-%d").date()
            days = (date.today() - surgery).days
            result = max(0, days)
            logger.debug(f"✅ Dias desde cirurgia: {result}")
            return result
        except Exception as e:
            logger.warning(f"days_since_surgery falhou: {e}")
            return None

    def _get_surgery_date(self, user: dict[str, Any] | Any) -> str | None:
        """
        Extrai a data da cirurgia.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Data em YYYY-MM-DD ou None
        """
        if isinstance(user, dict):
            return user.get("surgery_date")
        return getattr(user, "surgery_date", None)

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE
    # ─────────────────────────────────────────────────────────────────────────

    def automatic_phase(self, days: int | None) -> str:
        """
        Determina a fase automática baseada em dias pós-cirurgia.
        
        Args:
            days: Dias pós-cirurgia
            
        Returns:
            Chave da fase
            
        Example:
            >>> phase = bariatric_service.automatic_phase(45)
            >>> print(phase)  # "soft"
        """
        if days is None:
            logger.debug("automatic_phase: dias não informados, retornando liquid")
            return "liquid"
        
        for phase, (start, end) in _PHASE_DAYS.items():
            if start <= days <= end:
                logger.debug(f"✅ Fase automática: {phase} ({days} dias)")
                return phase
        
        logger.debug(f"✅ Fase automática: maintenance ({days} dias)")
        return "maintenance"

    def current_phase_data(self, phase_key: str) -> BariatricPhase:
        """
        Retorna dados completos da fase.
        
        Args:
            phase_key: Chave da fase
            
        Returns:
            Objeto BariatricPhase
            
        Example:
            >>> phase_data = bariatric_service.current_phase_data("liquid")
            >>> print(f"{phase_data.name}: max {phase_data.max_ml}ml")
        """
        if not phase_key:
            logger.warning("current_phase_data: phase_key não informado")
            phase_key = "liquid"
        
        data = config.BARIATRIC_PHASES.get(phase_key, {})
        
        phase = BariatricPhase(
            key=phase_key,
            name=data.get("name", "—"),
            days_range=data.get("days", "—"),
            max_ml=int(data.get("max_ml", 999)),
            max_cal=int(data.get("max_cal", 9999)),
            description=_PHASE_DESCRIPTIONS.get(phase_key, ""),
        )
        
        logger.debug(f"✅ Dados da fase: {phase.name}")
        return phase

    def get_phase_by_days(self, days: int | None) -> BariatricPhase:
        """
        Retorna dados completos da fase baseada em dias pós-cirurgia.
        
        Combina automatic_phase + current_phase_data em um único método.
        
        Args:
            days: Dias pós-cirurgia
            
        Returns:
            Objeto BariatricPhase
            
        Example:
            >>> phase = bariatric_service.get_phase_by_days(45)
            >>> print(f"{phase.name}: max {phase.max_ml}ml")
        """
        phase_key = self.automatic_phase(days)
        return self.current_phase_data(phase_key)

    def get_all_phases(self) -> list[BariatricPhase]:
        """
        Retorna todas as fases disponíveis.
        
        Returns:
            Lista de objetos BariatricPhase
            
        Example:
            >>> phases = bariatric_service.get_all_phases()
            >>> for p in phases:
            ...     print(f"{p.phase_number}: {p.name}")
        """
        phases = []
        for key in _PHASE_ORDER:
            phases.append(self.current_phase_data(key))
        
        logger.debug(f"✅ {len(phases)} fases disponíveis")
        return phases

    # ─────────────────────────────────────────────────────────────────────────
    # PROGRESS
    # ─────────────────────────────────────────────────────────────────────────

    def journey_progress(self, days: int | None) -> BariatricProgress:
        """
        Calcula progresso da jornada pós-bariátrica.
        
        Args:
            days: Dias pós-cirurgia
            
        Returns:
            Objeto BariatricProgress
            
        Example:
            >>> progress = bariatric_service.journey_progress(180)
            >>> print(f"{progress.percentage}%")
        """
        if days is None:
            return BariatricProgress(
                days=0,
                target_days=_TARGET_DAYS,
                percentage=0,
                remaining_days=_TARGET_DAYS,
                phase=self.current_phase_data("liquid"),
            )
        
        percentage = min(100, int(days / _TARGET_DAYS * 100))
        remaining = max(0, _TARGET_DAYS - days)
        
        phase_key = self.automatic_phase(days)
        phase = self.current_phase_data(phase_key)
        
        progress = BariatricProgress(
            days=days,
            target_days=_TARGET_DAYS,
            percentage=percentage,
            remaining_days=remaining,
            phase=phase,
        )
        
        logger.debug(f"✅ Progresso: {percentage}% ({days}/{_TARGET_DAYS} dias)")
        return progress

    def get_weight_loss(self, user: dict[str, Any] | Any) -> float | None:
        """
        Calcula perda de peso em kg.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Perda de peso em kg ou None
            
        Example:
            >>> loss = bariatric_service.get_weight_loss(user)
            >>> if loss:
            ...     print(f"Perda: {loss:.1f} kg")
        """
        # Busca cirurgia
        surgery = self.db.get_surgery()
        
        if not surgery:
            logger.debug("get_weight_loss: sem cirurgia registrada")
            return None
        
        # Extrai peso pré-cirurgia
        pre_weight = surgery.peso_pre if hasattr(surgery, "peso_pre") else surgery.get("peso_pre_cirurgia")
        
        if not pre_weight or pre_weight <= 0:
            logger.debug("get_weight_loss: sem peso pré-cirurgia")
            return None
        
        # Extrai peso atual
        if isinstance(user, dict):
            current_weight = user.get("current_weight")
        else:
            current_weight = getattr(user, "current_weight", None)
        
        if not current_weight or current_weight <= 0:
            logger.debug("get_weight_loss: sem peso atual")
            return None
        
        # Calcula perda
        loss = pre_weight - current_weight
        result = round(max(0, loss), 1)
        
        logger.debug(f"✅ Perda de peso: {result:.1f} kg")
        return result

    def get_weight_loss_percentage(self, user: dict[str, Any] | Any) -> float | None:
        """
        Calcula perda de peso em porcentagem.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Perda de peso em % ou None
            
        Example:
            >>> pct = bariatric_service.get_weight_loss_percentage(user)
            >>> if pct:
            ...     print(f"Perda: {pct:.1f}%")
        """
        # Busca cirurgia
        surgery = self.db.get_surgery()
        
        if not surgery:
            logger.debug("get_weight_loss_percentage: sem cirurgia registrada")
            return None
        
        # Extrai peso pré-cirurgia
        pre_weight = surgery.peso_pre if hasattr(surgery, "peso_pre") else surgery.get("peso_pre_cirurgia")
        
        if not pre_weight or pre_weight <= 0:
            logger.debug("get_weight_loss_percentage: sem peso pré-cirurgia")
            return None
        
        # Extrai peso atual
        if isinstance(user, dict):
            current_weight = user.get("current_weight")
        else:
            current_weight = getattr(user, "current_weight", None)
        
        if not current_weight or current_weight <= 0:
            logger.debug("get_weight_loss_percentage: sem peso atual")
            return None
        
        # Calcula perda percentual
        loss = pre_weight - current_weight
        percentage = (loss / pre_weight) * 100
        result = round(max(0, percentage), 1)
        
        logger.debug(f"✅ Perda de peso: {result:.1f}%")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # SUPPLEMENTS
    # ─────────────────────────────────────────────────────────────────────────

    def phase_supplements(self, phase_key: str) -> list[BariatricSupplement]:
        """
        Retorna lista de suplementos obrigatórios para a fase.
        
        Args:
            phase_key: Chave da fase
            
        Returns:
            Lista de objetos BariatricSupplement
            
        Example:
            >>> supplements = bariatric_service.phase_supplements("liquid")
            >>> for s in supplements:
            ...     print(f"{s.name}: {s.display_dose}")
        """
        if not phase_key:
            logger.warning("phase_supplements: phase_key não informado")
            return []
        
        # Busca nomes dos suplementos da fase
        supplement_names = _PHASE_SUPPLEMENTS.get(phase_key, [])
        
        # Mapeia para dados completos
        all_supplements = {e["name"]: e for e in BARIATRIC_ESSENTIALS}
        
        result = []
        for name in supplement_names:
            if name in all_supplements:
                data = all_supplements[name]
                result.append(BariatricSupplement(
                    name=name,
                    dose=data.get("dose", "—"),
                    unit=data.get("unit", ""),
                    phase=phase_key,
                    is_essential=True,
                ))
            else:
                # Suplemento não encontrado na lista essencial
                result.append(BariatricSupplement(
                    name=name,
                    dose="—",
                    unit="",
                    phase=phase_key,
                    is_essential=False,
                ))
        
        logger.debug(f"✅ {len(result)} suplementos para fase {phase_key}")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # ALERTS
    # ─────────────────────────────────────────────────────────────────────────

    def alerts(self, phase_key: str, user: dict[str, Any] | Any) -> list[BariatricAlert]:
        """
        Gera alertas nutricionais para o paciente bariátrico.
        
        Args:
            phase_key: Chave da fase atual
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Lista de objetos BariatricAlert
            
        Example:
            >>> alerts = bariatric_service.alerts("liquid", user)
            >>> for a in alerts:
            ...     print(f"{a.severity_icon} {a.title}: {a.message}")
        """
        if not phase_key:
            logger.warning("alerts: phase_key não informado")
            return []
        
        alerts = []
        
        try:
            phase_data = self.current_phase_data(phase_key)
            
            # Busca sumário diário
            daily_summary = self._nutrition_service.daily_summary()
            
            # Alerta de volume
            volume_alert = self._check_volume_alert(daily_summary, phase_data)
            if volume_alert:
                alerts.append(volume_alert)
            
            # Alerta de calorias
            calorie_alert = self._check_calorie_alert(daily_summary, phase_data)
            if calorie_alert:
                alerts.append(calorie_alert)
            
            # Alerta de proteína
            protein_alert = self._check_protein_alert(daily_summary, user)
            if protein_alert:
                alerts.append(protein_alert)
            
            # Alerta de mudança de fase
            phase_alert = self._check_phase_change_alert(user, phase_key)
            if phase_alert:
                alerts.append(phase_alert)
            
            if alerts:
                logger.info(f"✅ {len(alerts)} alertas gerados")
            
            return alerts
            
        except Exception as e:
            logger.error(f"alerts falhou: {e}")
            return []

    def _check_volume_alert(
        self,
        daily_summary: dict[str, Any],
        phase_data: BariatricPhase,
    ) -> BariatricAlert | None:
        """
        Verifica alerta de volume.
        
        Args:
            daily_summary: Sumário diário
            phase_data: Dados da fase
            
        Returns:
            BariatricAlert ou None
        """
        volume = float(daily_summary.get("volume_ml", 0))
        max_ml = phase_data.max_ml
        
        if volume > 0 and volume > max_ml:
            return BariatricAlert(
                type="volume",
                severity="error" if volume > max_ml * 1.2 else "warning",
                title="🔪 Volume excedido",
                message=f"Volume: {volume:.0f}ml (máx {max_ml}ml na fase {phase_data.name})",
                action="Fracione as refeições em porções menores.",
            )
        elif volume > 0 and volume > max_ml * _ALERT_VOLUME_PCT:
            return BariatricAlert(
                type="volume",
                severity="warning",
                title="⚠️ Volume próximo do limite",
                message=f"Volume: {volume:.0f}ml (limite {max_ml}ml)",
                action="Atenção ao volume das próximas refeições.",
            )
        
        return None

    def _check_calorie_alert(
        self,
        daily_summary: dict[str, Any],
        phase_data: BariatricPhase,
    ) -> BariatricAlert | None:
        """
        Verifica alerta de calorias.
        
        Args:
            daily_summary: Sumário diário
            phase_data: Dados da fase
            
        Returns:
            BariatricAlert ou None
        """
        calories = int(daily_summary.get("calories", 0))
        max_cal = phase_data.max_cal
        
        if calories > 0 and calories > max_cal:
            return BariatricAlert(
                type="calorie",
                severity="error" if calories > max_cal * 1.2 else "warning",
                title="⚡ Calorias acima do limite",
                message=f"Calorias: {calories:.0f} kcal (máx {max_cal} kcal na fase {phase_data.name})",
                action="Priorize alimentos de alta densidade nutricional.",
            )
        elif calories > 0 and calories > max_cal * _ALERT_CALORIE_PCT:
            return BariatricAlert(
                type="calorie",
                severity="warning",
                title="⚠️ Calorias próximas do limite",
                message=f"Calorias: {calories:.0f} kcal (limite {max_cal} kcal)",
                action="Monitore a densidade calórica das refeições.",
            )
        
        return None

    def _check_protein_alert(
        self,
        daily_summary: dict[str, Any],
        user: dict[str, Any] | Any,
    ) -> BariatricAlert | None:
        """
        Verifica alerta de proteína.
        
        Args:
            daily_summary: Sumário diário
            user: Dados do usuário
            
        Returns:
            BariatricAlert ou None
        """
        protein = float(daily_summary.get("protein", 0))
        
        if protein <= 0:
            return None
        
        # Obtém peso
        if isinstance(user, dict):
            weight = user.get("current_weight", 70)
        else:
            weight = getattr(user, "current_weight", 70)
        
        if not weight or weight <= 0:
            weight = 70
        
        # Meta de proteína para bariátrico: 1.5g/kg
        protein_goal = weight * _PROTEIN_GOAL_PER_KG
        
        if protein < protein_goal * _PROTEIN_MIN_PCT:
            return BariatricAlert(
                type="protein",
                severity="error" if protein < protein_goal * _PROTEIN_CRITICAL_PCT else "warning",
                title="🥩 Proteína baixa",
                message=f"Proteína: {protein:.0f}g de {protein_goal:.0f}g (meta: {_PROTEIN_GOAL_PER_KG}g/kg)",
                action="Priorize fontes proteicas em cada refeição.",
            )
        
        return None

    def _check_phase_change_alert(
        self,
        user: dict[str, Any] | Any,
        current_phase: str,
    ) -> BariatricAlert | None:
        """
        Verifica alerta de mudança de fase.
        
        Args:
            user: Dados do usuário
            current_phase: Fase atual
            
        Returns:
            BariatricAlert ou None
        """
        days = self.days_since_surgery(user)
        
        if days is None:
            return None
        
        # Verifica se está próximo de mudar de fase
        current_index = _PHASE_ORDER.index(current_phase) if current_phase in _PHASE_ORDER else 0
        
        if current_index + 1 >= len(_PHASE_ORDER):
            return None
        
        next_phase = _PHASE_ORDER[current_index + 1]
        next_phase_data = self.current_phase_data(next_phase)
        
        # Dias até a próxima fase
        next_start = _PHASE_DAYS[next_phase][0]
        days_until = next_start - days
        
        if 0 < days_until <= _DAYS_UNTIL_PHASE_CHANGE:
            return BariatricAlert(
                type="phase",
                severity="info",
                title=f"📋 Próxima fase: {next_phase_data.name}",
                message=f"Em {days_until} dia(s) você poderá iniciar a fase {next_phase_data.name}",
                action=f"Prepare-se para transição: {next_phase_data.description}",
            )
        
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────────

    def summary(self, user: dict[str, Any] | Any) -> BariatricSummary:
        """
        Retorna resumo completo do acompanhamento bariátrico.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto BariatricSummary com resumo completo
            
        Example:
            >>> summary = bariatric_service.summary(user)
            >>> print(f"Fase: {summary.phase.name}")
            >>> print(f"Progresso: {summary.progress.percentage}%")
            >>> print(f"Suplementos: {len(summary.supplements)}")
        """
        if not user:
            logger.warning("summary: user não informado")
            return self._empty_summary()
        
        # Dias desde cirurgia
        days = self.days_since_surgery(user)
        
        # Fase atual (preferência: usuário > automática)
        if isinstance(user, dict):
            phase_key = user.get("bariatric_phase")
        else:
            phase_key = getattr(user, "bariatric_phase", None)
        
        if not phase_key or phase_key not in _PHASE_ORDER:
            phase_key = self.automatic_phase(days)
        
        phase = self.current_phase_data(phase_key)
        
        # Tipo de cirurgia
        surgery_type = self._get_surgery_type(user)
        
        # Progresso
        progress = self.journey_progress(days)
        
        # Suplementos
        supplements = self.phase_supplements(phase_key)
        
        # Alertas
        alerts = self.alerts(phase_key, user)
        
        # Dados da cirurgia
        surgery = self.db.get_surgery()
        surgery_date = None
        pre_surgery_weight = None
        
        if surgery:
            surgery_date = surgery.data_cirurgia if hasattr(surgery, "data_cirurgia") else surgery.get("data_cirurgia")
            pre_surgery_weight = surgery.peso_pre if hasattr(surgery, "peso_pre") else surgery.get("peso_pre_cirurgia")
        
        summary = BariatricSummary(
            phase=phase,
            days=days,
            surgery_type=surgery_type,
            progress=progress,
            supplements=supplements,
            alerts=alerts,
            surgery_date=surgery_date,
            pre_surgery_weight=pre_surgery_weight,
        )
        
        logger.debug(f"✅ Resumo bariátrico: {phase.name} - {progress.percentage}%")
        return summary

    def _empty_summary(self) -> BariatricSummary:
        """Retorna resumo vazio."""
        return BariatricSummary(
            phase=self.current_phase_data("liquid"),
            days=None,
            surgery_type="—",
            progress=BariatricProgress(
                days=0,
                target_days=_TARGET_DAYS,
                percentage=0,
                remaining_days=_TARGET_DAYS,
                phase=self.current_phase_data("liquid"),
            ),
            supplements=[],
            alerts=[],
        )

    def _get_surgery_type(self, user: dict[str, Any] | Any) -> str:
        """
        Extrai tipo de cirurgia do usuário ou banco.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Tipo de cirurgia formatado
        """
        # Tenta do usuário
        if isinstance(user, dict):
            surgery_type = user.get("bariatric_type", "")
        else:
            surgery_type = getattr(user, "bariatric_type", "")
        
        if not surgery_type:
            # Tenta do banco
            surgery = self.db.get_surgery()
            if surgery:
                surgery_type = surgery.tipo if hasattr(surgery, "tipo") else surgery.get("tipo_cirurgia", "")
        
        # Tipo de cirurgia (label)
        return config.BARIATRIC_TYPES.get(surgery_type, surgery_type or "—")

    # ─────────────────────────────────────────────────────────────────────────
    # STATISTICS
    # ─────────────────────────────────────────────────────────────────────────

    def get_bariatric_stats(self, user: dict[str, Any] | Any) -> BariatricStats:
        """
        Retorna estatísticas detalhadas do acompanhamento bariátrico.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto BariatricStats com estatísticas
            
        Example:
            >>> stats = bariatric_service.get_bariatric_stats(user)
            >>> print(f"Mudanças de fase: {stats.total_phase_changes}")
            >>> print(f"Média de volume: {stats.average_volume_ml}ml")
            >>> print(f"Perda de peso: {stats.weight_loss_label}")
        """
        if not user:
            logger.warning("get_bariatric_stats: user não informado")
            return BariatricStats()
        
        try:
            # Busca histórico de fases
            phase_history = self.db.get_phases_history()
            
            total_phase_changes = len(phase_history) - 1 if phase_history else 0
            
            # Dias na fase atual
            days = self.days_since_surgery(user)
            days_in_current_phase = self._calculate_days_in_current_phase(phase_history, days)
            
            # Média de volume (de refeições)
            meals = self.db.get_meals(30)
            average_volume = self._calculate_average_volume(meals)
            
            # Média de calorias
            average_calories = self._calculate_average_calories(meals)
            
            # Última mudança de fase
            last_phase_change = self._get_last_phase_change(phase_history)
            
            # Adesão à suplementação
            supplement_adherence = self._calculate_supplement_adherence(user)
            
            # Perda de peso
            weight_loss = self.get_weight_loss(user) or 0.0
            weight_loss_pct = self.get_weight_loss_percentage(user) or 0.0
            
            stats = BariatricStats(
                total_phase_changes=total_phase_changes,
                days_in_current_phase=days_in_current_phase,
                average_volume_ml=average_volume,
                average_calories=average_calories,
                supplement_adherence=supplement_adherence,
                last_phase_change=last_phase_change,
                weight_loss_kg=weight_loss,
                weight_loss_percentage=weight_loss_pct,
            )
            
            logger.debug(f"✅ Stats bariátricas: {total_phase_changes} mudanças de fase")
            return stats
            
        except Exception as e:
            logger.error(f"get_bariatric_stats falhou: {e}")
            return BariatricStats()

    def _calculate_days_in_current_phase(
        self,
        phase_history: list,
        days: int | None,
    ) -> int:
        """Calcula dias na fase atual."""
        if not phase_history or not days:
            return 0
        
        try:
            latest = phase_history[0]
            if hasattr(latest, "iniciada_em"):
                start_date = latest.iniciada_em
            else:
                start_date = latest.get("iniciada_em", "")
            
            if start_date:
                start = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
                return (date.today() - start).days
        except Exception as e:
            logger.debug(f"Erro ao calcular dias na fase: {e}")
        
        return 0

    def _calculate_average_volume(self, meals: list) -> float:
        """Calcula volume médio por refeição."""
        try:
            volumes = [m.volume_ml for m in meals if m.volume_ml > 0]
            return round(sum(volumes) / len(volumes), 1) if volumes else 0.0
        except Exception:
            return 0.0

    def _calculate_average_calories(self, meals: list) -> float:
        """Calcula média de calorias diárias."""
        try:
            calories = [m.calories for m in meals]
            return round(sum(calories) / len(calories), 0) if calories else 0.0
        except Exception:
            return 0.0

    def _get_last_phase_change(self, phase_history: list) -> str | None:
        """Retorna data da última mudança de fase."""
        if not phase_history or len(phase_history) <= 1:
            return None
        
        try:
            latest = phase_history[0]
            if hasattr(latest, "iniciada_em"):
                return latest.iniciada_em
            return latest.get("iniciada_em")
        except Exception:
            return None

    def _calculate_supplement_adherence(self, user: dict[str, Any] | Any) -> float:
        """
        Calcula adesão à suplementação.
        
        Args:
            user: Dados do usuário
            
        Returns:
            Percentual de adesão (0-100)
        """
        try:
            # Busca suplementos registrados
            supplements = self.db.get_supplements(30)
            
            # Pega suplementos obrigatórios da fase atual
            summary = self.summary(user)
            required = len(summary.supplements)
            
            if required == 0:
                return 100.0
            
            # Conta suplementos registrados
            required_names = {sup.name for sup in summary.supplements}
            registered = sum(1 for s in supplements if s.name in required_names)
            
            adherence = min(100.0, round(registered / required * 100, 1))
            logger.debug(f"✅ Adesão à suplementação: {adherence}%")
            return adherence
            
        except Exception as e:
            logger.debug(f"_calculate_supplement_adherence falhou: {e}")
            return 100.0

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def is_bariatric_user(self, user: dict[str, Any] | Any) -> bool:
        """
        Verifica se o usuário é bariátrico.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            True se for usuário bariátrico
            
        Example:
            >>> if bariatric_service.is_bariatric_user(user):
            ...     print("Paciente bariátrico")
        """
        if not user:
            return False
        
        # Verifica health_mode
        if isinstance(user, dict):
            health_mode = user.get("health_mode", "")
            is_bariatric = user.get("is_bariatric", False)
        else:
            health_mode = getattr(user, "health_mode", "")
            is_bariatric = getattr(user, "is_bariatric", False)
        
        if health_mode == "bariatric" or is_bariatric:
            return True
        
        # Verifica se tem cirurgia registrada
        surgery = self.db.get_surgery()
        return surgery is not None

    # ─────────────────────────────────────────────────────────────────────────
    # ALIASES (COMPATIBILIDADE)
    # ─────────────────────────────────────────────────────────────────────────

    def dias_pos_cirurgia(self, user: dict[str, Any] | Any) -> int | None:
        """Alias para days_since_surgery (compatibilidade)."""
        return self.days_since_surgery(user)

    def fase_automatica(self, days: int | None) -> str:
        """Alias para automatic_phase (compatibilidade)."""
        return self.automatic_phase(days)

    def fase_data(self, phase_key: str) -> BariatricPhase:
        """Alias para current_phase_data (compatibilidade)."""
        return self.current_phase_data(phase_key)

    def progresso_jornada(self, days: int | None) -> BariatricProgress:
        """Alias para journey_progress (compatibilidade)."""
        return self.journey_progress(days)

    def suplementos_fase(self, phase_key: str) -> list[BariatricSupplement]:
        """Alias para phase_supplements (compatibilidade)."""
        return self.phase_supplements(phase_key)

    def alertas(self, phase_key: str, user: dict[str, Any] | Any) -> list[BariatricAlert]:
        """Alias para alerts (compatibilidade)."""
        return self.alerts(phase_key, user)

    def resumo(self, user: dict[str, Any] | Any) -> BariatricSummary:
        """Alias para summary (compatibilidade)."""
        return self.summary(user)


__all__ = [
    "BariatricService",
    "BariatricPhase",
    "BariatricProgress",
    "BariatricSupplement",
    "BariatricAlert",
    "BariatricSummary",
    "BariatricStats",
]
