"""
Melshape — Score Service.

Traduz vw_score_transformacao em:
- Narrativa humana para o paciente (nunca número cru)
- Recomendação de ação para o profissional

Princípios:
- Nunca exibir número cru para o paciente — sempre contexto emocional
- Score é ferramenta de ação, não de julgamento
- Recomendações acionáveis para o profissional
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    ScoreService
    ├── Data
    │   └── get_score(patient_id) -> ScoreData | None
    ├── Patient Narrative
    │   └── patient_narrative(user) -> Narrative
    ├── Professional Recommendation
    │   └── professional_recommendation(patient_id) -> Recommendation
    ├── Summary
    │   └── get_score_summary(patient_id) -> ScoreSummary
    └── Utilities
        └── _determine_narrative_level(score) -> NarrativeLevel
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from core.database import Database

logger = logging.getLogger("Melshape.Score")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds de score
_THRESHOLD_EXCELLENT: int = 80
_THRESHOLD_GOOD: int = 60
_THRESHOLD_MODERATE: int = 40
_THRESHOLD_LOW: int = 20

# Thresholds para áreas fracas e fortes
_WEAKNESS_THRESHOLD: float = 40.0
_STRENGTH_THRESHOLD: float = 80.0

# Pesos para recomendações
_WEIGHT_ADHERENCE: float = 0.25
_WEIGHT_ENGAGEMENT: float = 0.20
_WEIGHT_NUTRITION: float = 0.20
_WEIGHT_BEHAVIOR: float = 0.15
_WEIGHT_CLINICAL: float = 0.20

# Recomendações por nível
_RECOMMENDATIONS: dict[str, list[dict[str, str]]] = {
    "excellent": [
        {"action": "Manter estratégia", "detail": "Paciente evoluindo bem. Reforçar hábitos positivos.", "urgency": "baixa"},
        {"action": "Consolidar hábitos", "detail": "Foco em manter consistência e evitar estagnação.", "urgency": "baixa"},
    ],
    "good": [
        {"action": "Acompanhamento regular", "detail": "Paciente no caminho certo. Manter suporte atual.", "urgency": "media"},
        {"action": "Ajustes finos", "detail": "Revisar pequenos ajustes para acelerar progresso.", "urgency": "media"},
    ],
    "moderate": [
        {"action": "Revisar protocolo", "detail": "Aderência ou engajamento moderado. Revisar estratégia.", "urgency": "media"},
        {"action": "Fortalecer vínculo", "detail": "Paciente precisa de mais suporte e acompanhamento.", "urgency": "media"},
    ],
    "low": [
        {"action": "Intervenção urgente", "detail": "Score baixo. Paciente precisa de atenção imediata.", "urgency": "alta"},
        {"action": "Reavaliar plano", "detail": "Revisar plano terapêutico e identificar barreiras.", "urgency": "alta"},
    ],
}

# Labels das áreas
_AREA_LABELS: dict[str, str] = {
    "aderencia": "Aderência alimentar",
    "engajamento": "Engajamento",
    "nutricao": "Nutrição",
    "comportamento": "Comportamento",
    "clinico": "Indicadores clínicos",
}


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class NarrativeLevel(str, Enum):
    """Níveis de narrativa do score de transformação."""
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    LOW = "low"
    EMPTY = "empty"
    
    @classmethod
    def from_score(cls, score: float) -> NarrativeLevel:
        """Determina o nível baseado no score."""
        if score >= _THRESHOLD_EXCELLENT:
            return cls.EXCELLENT
        elif score >= _THRESHOLD_GOOD:
            return cls.GOOD
        elif score >= _THRESHOLD_MODERATE:
            return cls.MODERATE
        elif score >= _THRESHOLD_LOW:
            return cls.LOW
        return cls.EMPTY
    
    @property
    def icon(self) -> str:
        """Retorna ícone do nível."""
        icons = {
            "excellent": "🏆",
            "good": "📈",
            "moderate": "⚡",
            "low": "🌱",
            "empty": "🗺️",
        }
        return icons.get(self.value, "📊")
    
    @property
    def color(self) -> str:
        """Retorna cor do nível."""
        colors = {
            "excellent": "var(--success)",
            "good": "var(--primary)",
            "moderate": "var(--warning)",
            "low": "var(--info)",
            "empty": "var(--text-muted)",
        }
        return colors.get(self.value, "var(--text-muted)")
    
    @property
    def label(self) -> str:
        """Retorna label do nível."""
        labels = {
            "excellent": "Transformação Avançada",
            "good": "Progresso Consistente",
            "moderate": "Caminho Certo",
            "low": "Primeiros Passos",
            "empty": "Comece sua Jornada",
        }
        return labels.get(self.value, "Em Progresso")
    
    @property
    def description(self) -> str:
        """Retorna descrição do nível."""
        descriptions = {
            "excellent": "Resultados excepcionais através de consistência",
            "good": "Evolução sólida e consistente",
            "moderate": "No caminho certo, pequenos ajustes necessários",
            "low": "Primeiros passos da jornada",
            "empty": "Ainda sem dados suficientes",
        }
        return descriptions.get(self.value, "Em progresso")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO DE SCORE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScoreData:
    """
    Dados completos do score de transformação.
    
    Attributes:
        patient_id: ID do paciente
        score_global: Score global (0-100)
        adherence: Aderência (0-100)
        engagement: Engajamento (0-100)
        nutrition: Nutrição (0-100)
        behavior: Comportamento (0-100)
        clinical: Indicadores clínicos (0-100)
        calculated_at: Data do cálculo
    """
    patient_id: str
    score_global: float
    adherence: float = 0.0
    engagement: float = 0.0
    nutrition: float = 0.0
    behavior: float = 0.0
    clinical: float = 0.0
    calculated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoreData:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            patient_id=data.get("patient_id", data.get("perfil_id", "")),
            score_global=float(data.get("score_global", data.get("score", 0))),
            adherence=float(data.get("aderencia", 0)),
            engagement=float(data.get("engajamento", 0)),
            nutrition=float(data.get("nutricao", 0)),
            behavior=float(data.get("comportamento", 0)),
            clinical=float(data.get("clinical", data.get("indicadores_clinicos", 0))),
            calculated_at=data.get("calculated_at", data.get("criado_em", "")),
        )
    
    @property
    def level(self) -> NarrativeLevel:
        """Retorna o nível do score."""
        return NarrativeLevel.from_score(self.score_global)
    
    @property
    def is_empty(self) -> bool:
        """Verifica se o score está vazio."""
        return self.score_global == 0
    
    @property
    def is_excellent(self) -> bool:
        """Verifica se o score é excelente."""
        return self.score_global >= _THRESHOLD_EXCELLENT
    
    @property
    def is_good(self) -> bool:
        """Verifica se o score é bom."""
        return _THRESHOLD_GOOD <= self.score_global < _THRESHOLD_EXCELLENT
    
    @property
    def is_moderate(self) -> bool:
        """Verifica se o score é moderado."""
        return _THRESHOLD_MODERATE <= self.score_global < _THRESHOLD_GOOD
    
    @property
    def is_low(self) -> bool:
        """Verifica se o score é baixo."""
        return _THRESHOLD_LOW <= self.score_global < _THRESHOLD_MODERATE
    
    @property
    def areas(self) -> dict[str, float]:
        """Retorna todas as áreas com seus valores."""
        return {
            "aderencia": self.adherence,
            "engajamento": self.engagement,
            "nutricao": self.nutrition,
            "comportamento": self.behavior,
            "clinico": self.clinical,
        }
    
    @property
    def weakest_area(self) -> str | None:
        """Retorna a área mais fraca."""
        areas = self.areas
        if not areas:
            return None
        return min(areas.items(), key=lambda x: x[1])[0]
    
    @property
    def strongest_area(self) -> str | None:
        """Retorna a área mais forte."""
        areas = self.areas
        if not areas:
            return None
        return max(areas.items(), key=lambda x: x[1])[0]
    
    @property
    def weakest_area_label(self) -> str:
        """Retorna label da área mais fraca."""
        area = self.weakest_area
        if not area:
            return "—"
        return _AREA_LABELS.get(area, area)
    
    @property
    def strongest_area_label(self) -> str:
        """Retorna label da área mais forte."""
        area = self.strongest_area
        if not area:
            return "—"
        return _AREA_LABELS.get(area, area)
    
    @property
    def weak_areas(self) -> list[str]:
        """Retorna lista de áreas fracas (< threshold)."""
        return [
            area for area, value in self.areas.items()
            if value < _WEAKNESS_THRESHOLD
        ]
    
    @property
    def strong_areas(self) -> list[str]:
        """Retorna lista de áreas fortes (>= threshold)."""
        return [
            area for area, value in self.areas.items()
            if value >= _STRENGTH_THRESHOLD
        ]
    
    @property
    def weak_areas_labels(self) -> list[str]:
        """Retorna labels das áreas fracas."""
        return [_AREA_LABELS.get(area, area) for area in self.weak_areas]
    
    @property
    def strong_areas_labels(self) -> list[str]:
        """Retorna labels das áreas fortes."""
        return [_AREA_LABELS.get(area, area) for area in self.strong_areas]


@dataclass(frozen=True)
class Narrative:
    """
    Narrativa do score para o paciente.
    
    Attributes:
        level: Nível da narrativa
        title: Título da narrativa
        message: Mensagem da narrativa
        icon: Ícone representativo
        color: Cor para exibição
        sub_message: Mensagem adicional (opcional)
    """
    level: NarrativeLevel
    title: str
    message: str
    icon: str
    color: str
    sub_message: str = ""
    
    @classmethod
    def from_level(cls, level: NarrativeLevel, score: float = 0) -> Narrative:
        """Cria uma narrativa a partir do nível."""
        narratives = {
            NarrativeLevel.EXCELLENT: Narrative(
                level=level,
                title="🏆 Transformação Avançada",
                message=(
                    "Sua consistência está gerando resultados excepcionais. "
                    "Você está entre os mais engajados da plataforma."
                ),
                icon="🏆",
                color="var(--success)",
                sub_message="Mantenha o foco — você é referência!",
            ),
            NarrativeLevel.GOOD: Narrative(
                level=level,
                title="📈 Progresso Consistente",
                message=(
                    "Você está evoluindo de forma sólida. "
                    "Continue com a consistência — os resultados estão chegando."
                ),
                icon="📈",
                color="var(--primary)",
                sub_message="Pequenos ajustes podem acelerar ainda mais.",
            ),
            NarrativeLevel.MODERATE: Narrative(
                level=level,
                title="⚡ Caminho Certo",
                message=(
                    "Você está no caminho certo. "
                    "Pequenos ajustes vão acelerar sua transformação."
                ),
                icon="⚡",
                color="var(--warning)",
                sub_message="Foque em um hábito por vez.",
            ),
            NarrativeLevel.LOW: Narrative(
                level=level,
                title="🌱 Primeiros Passos",
                message=(
                    "Cada dia que você registra é um passo real. "
                    "Continue — a consistência se constrói aos poucos."
                ),
                icon="🌱",
                color="var(--info)",
                sub_message="Você já começou. Isso é o mais importante.",
            ),
            NarrativeLevel.EMPTY: Narrative(
                level=level,
                title="🗺️ Comece sua Jornada",
                message=(
                    "Registre seus dados para ver seu score de transformação."
                ),
                icon="🗺️",
                color="var(--text-muted)",
                sub_message="O primeiro passo é o mais importante.",
            ),
        }
        return narratives.get(level, narratives[NarrativeLevel.EMPTY])
    
    @classmethod
    def with_name(cls, level: NarrativeLevel, name: str) -> Narrative:
        """Cria uma narrativa personalizada com nome do paciente."""
        base = cls.from_level(level)
        
        if not name or level == NarrativeLevel.EMPTY:
            return base
        
        # Adiciona nome ao título
        title_parts = base.title.split(" ", 1)
        if len(title_parts) > 1:
            new_title = f"{title_parts[0]} {name} — {title_parts[1]}"
        else:
            new_title = f"{base.title} {name}"
        
        return Narrative(
            level=base.level,
            title=new_title,
            message=base.message,
            icon=base.icon,
            color=base.color,
            sub_message=base.sub_message,
        )
    
    @property
    def is_empty(self) -> bool:
        """Verifica se a narrativa está vazia."""
        return self.level == NarrativeLevel.EMPTY
    
    @property
    def level_label(self) -> str:
        """Retorna label do nível."""
        return self.level.label
    
    @property
    def level_description(self) -> str:
        """Retorna descrição do nível."""
        return self.level.description


@dataclass(frozen=True)
class Recommendation:
    """
    Recomendação para o profissional.
    
    Attributes:
        action: Ação recomendada
        urgency: Urgência da ação (alta/media/baixa)
        message: Mensagem da recomendação
        score: Score atual
        weaknesses: Lista de áreas fracas
        strengths: Lista de áreas fortes
    """
    action: str
    urgency: str
    message: str
    score: float
    weaknesses: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    
    @classmethod
    def from_data(cls, score_data: ScoreData) -> Recommendation:
        """Cria uma recomendação a partir dos dados de score."""
        level = score_data.level
        
        if score_data.is_empty:
            return cls(
                action="Aguardar dados",
                urgency="baixa",
                message="Paciente ainda sem dados suficientes.",
                score=score_data.score_global,
            )
        
        # Determina ação baseada no nível
        recommendations = _RECOMMENDATIONS.get(level.value, _RECOMMENDATIONS["low"])
        rec = recommendations[0]
        
        # Identifica áreas fracas e fortes
        weak_labels = score_data.weak_areas_labels
        strong_labels = score_data.strong_areas_labels
        
        # Gera mensagem personalizada
        message = rec["detail"]
        if weak_labels:
            message += f" Foco em: {', '.join(weak_labels)}."
        if strong_labels:
            message += f" Pontos fortes: {', '.join(strong_labels)}."
        
        return cls(
            action=rec["action"],
            urgency=rec["urgency"],
            message=message,
            score=score_data.score_global,
            weaknesses=weak_labels,
            strengths=strong_labels,
        )
    
    @classmethod
    def empty(cls) -> Recommendation:
        """Cria uma recomendação vazia."""
        return cls(
            action="Aguardar dados",
            urgency="baixa",
            message="Paciente ainda sem dados suficientes.",
            score=0,
        )
    
    @classmethod
    def error(cls) -> Recommendation:
        """Cria uma recomendação de erro."""
        return cls(
            action="Erro ao gerar recomendação",
            urgency="media",
            message="Tente novamente mais tarde.",
            score=0,
        )
    
    @property
    def urgency_icon(self) -> str:
        """Retorna ícone da urgência."""
        icons = {
            "alta": "🚨",
            "media": "⚠️",
            "baixa": "✅",
        }
        return icons.get(self.urgency, "📋")
    
    @property
    def urgency_label(self) -> str:
        """Retorna label da urgência."""
        labels = {
            "alta": "Alta",
            "media": "Média",
            "baixa": "Baixa",
        }
        return labels.get(self.urgency, "Normal")
    
    @property
    def is_urgent(self) -> bool:
        """Verifica se a ação é urgente."""
        return self.urgency == "alta"
    
    @property
    def has_weaknesses(self) -> bool:
        """Verifica se há áreas fracas identificadas."""
        return len(self.weaknesses) > 0
    
    @property
    def has_strengths(self) -> bool:
        """Verifica se há áreas fortes identificadas."""
        return len(self.strengths) > 0
    
    @property
    def display_text(self) -> str:
        """Retorna texto formatado para exibição."""
        return f"{self.urgency_icon} {self.action}: {self.message}"


@dataclass(frozen=True)
class ScoreSummary:
    """
    Resumo do score para exibição.
    
    Attributes:
        score: Score global (0-100)
        level: Nível do score
        level_label: Label do nível
        level_icon: Ícone do nível
        level_color: Cor do nível
        has_data: Se há dados disponíveis
        weakest_area: Área mais fraca
        strongest_area: Área mais forte
        weak_count: Quantidade de áreas fracas
        strong_count: Quantidade de áreas fortes
    """
    score: float = 0.0
    level: str = "empty"
    level_label: str = "Sem dados"
    level_icon: str = "🗺️"
    level_color: str = "var(--text-muted)"
    has_data: bool = False
    weakest_area: str = "—"
    strongest_area: str = "—"
    weak_count: int = 0
    strong_count: int = 0
    
    @classmethod
    def from_score_data(cls, score_data: ScoreData | None) -> ScoreSummary:
        """Cria um resumo a partir dos dados de score."""
        if not score_data or score_data.is_empty:
            return cls()
        
        return cls(
            score=round(score_data.score_global, 0),
            level=score_data.level.value,
            level_label=score_data.level.label,
            level_icon=score_data.level.icon,
            level_color=score_data.level.color,
            has_data=True,
            weakest_area=score_data.weakest_area_label,
            strongest_area=score_data.strongest_area_label,
            weak_count=len(score_data.weak_areas),
            strong_count=len(score_data.strong_areas),
        )
    
    @property
    def score_int(self) -> int:
        """Retorna score como inteiro."""
        return int(self.score)
    
    @property
    def is_empty(self) -> bool:
        """Verifica se está vazio."""
        return not self.has_data
    
    @property
    def has_imbalance(self) -> bool:
        """Verifica se há desequilíbrio entre áreas."""
        return self.weak_count > 0 and self.strong_count > 0


# ─────────────────────────────────────────────────────────────────────────────
# SCORE SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class ScoreService:
    """
    Serviço de score de transformação.
    
    Traduz dados do score em narrativa para paciente e recomendações para profissional.
    
    Example:
        >>> db = Database()
        >>> score_service = ScoreService(db)
        >>> narrative = score_service.patient_narrative(user)
        >>> print(f"{narrative.icon} {narrative.title}")
        >>> print(narrative.message)
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de score.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ ScoreService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # DATA
    # ─────────────────────────────────────────────────────────────────────────

    def get_score(self, patient_id: str | None = None) -> ScoreData | None:
        """
        Busca dados do score de transformação.
        
        Args:
            patient_id: ID do paciente (padrão: usuário logado)
            
        Returns:
            Objeto ScoreData ou None se não disponível
            
        Example:
            >>> score_data = score_service.get_score()
            >>> if score_data:
            ...     print(f"Score: {score_data.score_global:.0f}")
            ...     print(f"Nível: {score_data.level.label}")
        """
        if not patient_id:
            patient_id = self.db.uid()
        
        if not patient_id:
            logger.warning("get_score: patient_id não informado")
            return None
        
        if not self.db.is_real or not self.db.client:
            logger.debug("get_score: modo offline")
            return None
        
        try:
            response = (
                self.db.client.table("vw_score_transformacao")
                .select(
                    "score_global, aderencia, engajamento, "
                    "nutricao, comportamento, indicadores_clinicos"
                )
                .eq("perfil_id", patient_id)
                .limit(1)
                .execute()
            )
            
            if response.data:
                row = response.data[0]
                score_data = ScoreData(
                    patient_id=patient_id,
                    score_global=float(row.get("score_global", 0)),
                    adherence=float(row.get("aderencia", 0)),
                    engagement=float(row.get("engajamento", 0)),
                    nutrition=float(row.get("nutricao", 0)),
                    behavior=float(row.get("comportamento", 0)),
                    clinical=float(row.get("indicadores_clinicos", 0)),
                )
                logger.debug(f"✅ Score obtido: {score_data.score_global:.0f}")
                return score_data
            
            logger.debug(f"get_score: sem dados para {patient_id}")
            return None
            
        except Exception as e:
            logger.warning(f"get_score: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # PATIENT NARRATIVE
    # ─────────────────────────────────────────────────────────────────────────

    def patient_narrative(self, user: dict[str, Any] | Any) -> Narrative:
        """
        Retorna narrativa do score para o paciente.
        
        Nunca exibe número cru — sempre contexto emocional.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto Narrative com título, mensagem, ícone e cor
            
        Example:
            >>> narrative = score_service.patient_narrative(user)
            >>> print(f"{narrative.icon} {narrative.title}")
            >>> print(narrative.message)
        """
        if not user:
            logger.warning("patient_narrative: user não informado")
            return Narrative.from_level(NarrativeLevel.EMPTY)
        
        try:
            # Busca score
            patient_id = self.db.uid()
            score_data = self.get_score(patient_id)
            
            if not score_data or score_data.is_empty:
                logger.debug("patient_narrative: sem dados de score")
                return Narrative.from_level(NarrativeLevel.EMPTY)
            
            # Cria narrativa
            level = score_data.level
            
            # Personaliza mensagem com nome se disponível
            name = self._extract_first_name(user)
            
            if name:
                narrative = Narrative.with_name(level, name)
            else:
                narrative = Narrative.from_level(level)
            
            logger.debug(f"✅ Narrativa gerada: {narrative.level.value}")
            return narrative
            
        except Exception as e:
            logger.error(f"patient_narrative falhou: {e}")
            return Narrative.from_level(NarrativeLevel.EMPTY)

    def _extract_first_name(self, user: dict[str, Any] | Any) -> str:
        """
        Extrai primeiro nome do usuário.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Primeiro nome ou string vazia
        """
        if isinstance(user, dict):
            name = user.get("name", "")
        else:
            name = getattr(user, "name", "") if hasattr(user, "name") else ""
        
        if name:
            return name.split()[0]
        return ""

    # ─────────────────────────────────────────────────────────────────────────
    # PROFESSIONAL RECOMMENDATION
    # ─────────────────────────────────────────────────────────────────────────

    def professional_recommendation(self, patient_id: str) -> Recommendation:
        """
        Traduz score em ação concreta para o profissional.
        
        Responde: "O que devo fazer com este paciente agora?"
        
        Args:
            patient_id: ID do paciente
            
        Returns:
            Objeto Recommendation com ação e urgência
            
        Example:
            >>> recommendation = score_service.professional_recommendation("patient_123")
            >>> print(f"{recommendation.urgency_icon} {recommendation.action}")
            >>> print(recommendation.message)
        """
        if not patient_id:
            logger.warning("professional_recommendation: patient_id não informado")
            return Recommendation.empty()
        
        try:
            # Busca score
            score_data = self.get_score(patient_id)
            
            if not score_data or score_data.is_empty:
                logger.debug(f"professional_recommendation: sem dados para {patient_id}")
                return Recommendation.empty()
            
            # Cria recomendação
            recommendation = Recommendation.from_data(score_data)
            
            logger.debug(
                f"✅ Recomendação gerada para {patient_id}: "
                f"{recommendation.action} ({recommendation.urgency})"
            )
            return recommendation
            
        except Exception as e:
            logger.error(f"professional_recommendation falhou: {e}")
            return Recommendation.error()

    # ─────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────────

    def get_score_summary(self, patient_id: str | None = None) -> ScoreSummary:
        """
        Retorna resumo do score para exibição.
        
        Args:
            patient_id: ID do paciente
            
        Returns:
            Objeto ScoreSummary com resumo
            
        Example:
            >>> summary = score_service.get_score_summary()
            >>> print(f"Score: {summary.score_int}")
            >>> print(f"Nível: {summary.level_label}")
        """
        score_data = self.get_score(patient_id)
        summary = ScoreSummary.from_score_data(score_data)
        
        logger.debug(f"✅ Resumo gerado: score={summary.score_int}, level={summary.level}")
        return summary

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def get_patient_score_level(self, patient_id: str | None = None) -> NarrativeLevel:
        """
        Retorna apenas o nível do score do paciente.
        
        Args:
            patient_id: ID do paciente
            
        Returns:
            Objeto NarrativeLevel
            
        Example:
            >>> level = score_service.get_patient_score_level()
            >>> print(f"Nível: {level.label}")
        """
        score_data = self.get_score(patient_id)
        
        if not score_data or score_data.is_empty:
            return NarrativeLevel.EMPTY
        
        return score_data.level

    def get_patient_weakest_area(self, patient_id: str | None = None) -> str:
        """
        Retorna a área mais fraca do paciente.
        
        Args:
            patient_id: ID do paciente
            
        Returns:
            Label da área mais fraca
            
        Example:
            >>> area = score_service.get_patient_weakest_area()
            >>> print(f"Área mais fraca: {area}")
        """
        score_data = self.get_score(patient_id)
        
        if not score_data or score_data.is_empty:
            return "—"
        
        return score_data.weakest_area_label


__all__ = [
    "ScoreService",
    "ScoreData",
    "Narrative",
    "Recommendation",
    "ScoreSummary",
    "NarrativeLevel",
]
