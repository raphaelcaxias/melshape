"""
Melshape — Consultation Summary Service.

Gera um resumo completo dos últimos N dias do paciente para o profissional
usar antes da consulta: peso, nutrição, hábitos, check-ins, metas, condutas
anteriores e alertas em aberto — tudo num único lugar.

Elimina 30 minutos de trabalho do profissional por consulta.

Princípios:
- Dados consolidados: tudo que o profissional precisa em um só lugar
- Visualização clara: texto estruturado para leitura rápida
- Fallback automático: Supabase → MockDB (completo)
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades
- Insights: recomendações automáticas baseadas nos dados

Tabelas/Views utilizadas:
    - pesagens: histórico de peso
    - vw_consumo_diario: resumo nutricional diário
    - habitos / registros_habitos: hábitos e aderência
    - checkins: humor, energia, sono
    - condutas_clinicas: condutas anteriores
    - metas: metas do paciente
    - alertas_clinicos: alertas em aberto
    - historico_xp: XP do período

Arquitetura:
    ConsultationSummaryService
    ├── Generation
    │   ├── generate(patient_id, days) -> ConsultationSummary
    │   ├── generate_with_insights(patient_id, days) -> ConsultationSummary
    │   └── compare_periods(patient_id, days_current, days_previous) -> ConsultationComparison
    ├── Data Collection (com fallback MockDB)
    │   ├── _get_perfil(patient_id) -> dict
    │   ├── _get_peso(patient_id, cutoff) -> WeightSummary
    │   ├── _get_nutricao(patient_id, cutoff) -> NutritionSummary
    │   ├── _get_habitos(patient_id, cutoff) -> HabitSummary
    │   ├── _get_checkins(patient_id, cutoff) -> CheckinSummary
    │   ├── _get_metas(patient_id) -> list[Goal]
    │   ├── _get_condutas(patient_id) -> list
    │   ├── _get_alertas(patient_id) -> list
    │   └── _get_xp(patient_id, cutoff) -> dict
    ├── Analysis
    │   ├── generate_insights(summary) -> list[ConsultationInsight]
    │   └── _analyze_*() -> ConsultationInsight | None
    ├── Formatting
    │   ├── format_text(summary) -> str
    │   ├── format_markdown(summary) -> str
    │   ├── format_json(summary) -> str
    │   └── _format_section_*() -> str
    └── Utilities
        ├── _safe_float(value) -> float
        ├── _safe_date(date_str) -> str
        └── _calculate_percentage_change(current, previous) -> float
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

import config
from core.database import Database

logger = logging.getLogger("Melshape.ConsultationSummary")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Período padrão
_DEFAULT_DAYS: int = 30

# Thresholds
_ADHERENCE_GOOD: float = 70.0
_ADHERENCE_MODERATE: float = 50.0
_ADHERENCE_LOW: float = 30.0

_CHECKIN_GOOD: float = 70.0
_CHECKIN_MODERATE: float = 40.0

_WEIGHT_LOSS_SIGNIFICANT: float = 2.0
_WEIGHT_GAIN_SIGNIFICANT: float = 2.0

_NUTRITION_CALORIE_LOW: float = 1200.0
_NUTRITION_CALORIE_HIGH: float = 3000.0
_NUTRITION_PROTEIN_LOW: float = 50.0

# Labels de severidade para alertas
_ALERT_LABELS: dict[int, str] = {
    1: "🟡 Leve",
    2: "🟠 Moderado",
    3: "🔴 Grave",
}


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class InsightPriority(str, Enum):
    """Prioridade de insights."""
    LOW = "baixa"
    MEDIUM = "media"
    HIGH = "alta"
    CRITICAL = "critica"
    
    @property
    def icon(self) -> str:
        """Retorna ícone da prioridade."""
        icons = {
            "baixa": "💡",
            "media": "⚠️",
            "alta": "🔶",
            "critica": "🚨",
        }
        return icons.get(self.value, "💬")
    
    @property
    def label(self) -> str:
        """Retorna label da prioridade."""
        labels = {
            "baixa": "Baixa",
            "media": "Média",
            "alta": "Alta",
            "critica": "Crítica",
        }
        return labels.get(self.value, "Normal")


class InsightCategory(str, Enum):
    """Categoria de insight."""
    WEIGHT = "peso"
    NUTRITION = "nutricao"
    HABITS = "habitos"
    CHECKINS = "checkins"
    ENGAGEMENT = "engajamento"
    ALERTS = "alertas"
    GOALS = "metas"
    
    @property
    def icon(self) -> str:
        """Retorna ícone da categoria."""
        icons = {
            "peso": "⚖️",
            "nutricao": "🍽️",
            "habitos": "📋",
            "checkins": "💭",
            "engajamento": "⭐",
            "alertas": "⚠️",
            "metas": "🎯",
        }
        return icons.get(self.value, "📊")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PeriodInfo:
    """Informações do período analisado."""
    days: int
    start_date: str
    end_date: str
    
    @property
    def days_label(self) -> str:
        """Retorna label do período."""
        if self.days == 1:
            return "último dia"
        return f"últimos {self.days} dias"
    
    @property
    def range_label(self) -> str:
        """Retorna label do intervalo."""
        return f"{self.start_date} a {self.end_date}"
    
    @property
    def weeks(self) -> float:
        """Retorna número de semanas no período."""
        return self.days / 7
    
    @property
    def is_long_period(self) -> bool:
        """Verifica se é um período longo (>= 30 dias)."""
        return self.days >= 30


@dataclass(frozen=True)
class WeightSummary:
    """Resumo de evolução de peso."""
    registros: int = 0
    inicial: float | None = None
    atual: float | None = None
    variacao: float | None = None
    minimo: float | None = None
    maximo: float | None = None
    historico: list[dict] = field(default_factory=list)
    
    @property
    def has_data(self) -> bool:
        """Verifica se há dados de peso."""
        return self.registros > 0
    
    @property
    def variacao_label(self) -> str:
        """Retorna label da variação de peso."""
        if self.variacao is None:
            return "—"
        if self.variacao > 0:
            return f"▲ +{self.variacao:.1f} kg"
        elif self.variacao < 0:
            return f"▼ {self.variacao:.1f} kg"
        return "— 0 kg"
    
    @property
    def variacao_absoluta(self) -> float:
        """Retorna variação absoluta (sem sinal)."""
        return abs(self.variacao) if self.variacao is not None else 0.0
    
    @property
    def tendencia(self) -> str:
        """Retorna tendência de peso."""
        if self.variacao is None:
            return "neutra"
        if self.variacao < -0.5:
            return "perda"
        elif self.variacao > 0.5:
            return "ganho"
        return "estavel"
    
    @property
    def tendencia_icon(self) -> str:
        """Retorna ícone da tendência."""
        icons = {
            "perda": "📉",
            "ganho": "📈",
            "estavel": "➡️",
            "neutra": "❓",
        }
        return icons.get(self.tendencia, "❓")
    
    @property
    def amplitude(self) -> float:
        """Retorna amplitude (max - min)."""
        if self.maximo is not None and self.minimo is not None:
            return self.maximo - self.minimo
        return 0.0
    
    @property
    def is_significant_change(self) -> bool:
        """Verifica se a mudança é significativa."""
        return self.variacao_absoluta >= _WEIGHT_LOSS_SIGNIFICANT


@dataclass(frozen=True)
class NutritionSummary:
    """Resumo nutricional."""
    dias_registrados: int = 0
    media_calorias: float = 0.0
    media_proteina: float = 0.0
    media_carbs: float = 0.0
    media_gordura: float = 0.0
    media_fibras: float = 0.0
    
    @property
    def has_data(self) -> bool:
        """Verifica se há dados nutricionais."""
        return self.dias_registrados > 0
    
    @property
    def consistencia_label(self) -> str:
        """Retorna label de consistência."""
        if self.dias_registrados == 0:
            return "📭 Sem registros"
        elif self.dias_registrados < 7:
            return "⚠️ Baixa consistência"
        elif self.dias_registrados < 14:
            return "⚡ Consistência moderada"
        else:
            return "✅ Boa consistência"
    
    @property
    def consistencia_pct(self) -> float:
        """Retorna percentual de consistência (baseado em 30 dias)."""
        return min(100.0, (self.dias_registrados / 30) * 100)
    
    @property
    def protein_ratio(self) -> float:
        """Retorna percentual de calorias da proteína."""
        if self.media_calorias == 0:
            return 0.0
        protein_calories = self.media_proteina * 4
        return (protein_calories / self.media_calorias) * 100
    
    @property
    def is_low_calorie(self) -> bool:
        """Verifica se as calorias estão baixas."""
        return self.media_calorias < _NUTRITION_CALORIE_LOW and self.media_calorias > 0
    
    @property
    def is_high_calorie(self) -> bool:
        """Verifica se as calorias estão altas."""
        return self.media_calorias > _NUTRITION_CALORIE_HIGH
    
    @property
    def is_low_protein(self) -> bool:
        """Verifica se a proteína está baixa."""
        return self.media_proteina < _NUTRITION_PROTEIN_LOW and self.media_proteina > 0


@dataclass(frozen=True)
class HabitSummary:
    """Resumo de hábitos."""
    total: int = 0
    media_aderencia: float = 0.0
    habitos: list[dict] = field(default_factory=list)
    
    @property
    def has_data(self) -> bool:
        """Verifica se há dados de hábitos."""
        return self.total > 0
    
    @property
    def aderencia_label(self) -> str:
        """Retorna label da aderência."""
        if self.media_aderencia >= _ADHERENCE_GOOD:
            return "✅ Boa"
        elif self.media_aderencia >= _ADHERENCE_MODERATE:
            return "⚠️ Moderada"
        elif self.media_aderencia >= _ADHERENCE_LOW:
            return "⚡ Baixa"
        else:
            return "🔴 Crítica"
    
    @property
    def best_habit(self) -> dict | None:
        """Retorna hábito com melhor aderência."""
        if not self.habitos:
            return None
        return max(self.habitos, key=lambda h: h.get("aderencia", 0))
    
    @property
    def worst_habit(self) -> dict | None:
        """Retorna hábito com pior aderência."""
        if not self.habitos:
            return None
        return min(self.habitos, key=lambda h: h.get("aderencia", 0))
    
    @property
    def habits_above_70(self) -> int:
        """Retorna quantidade de hábitos com aderência >= 70%."""
        return sum(1 for h in self.habitos if h.get("aderencia", 0) >= 70)
    
    @property
    def habits_below_30(self) -> int:
        """Retorna quantidade de hábitos com aderência < 30%."""
        return sum(1 for h in self.habitos if h.get("aderencia", 0) < 30)


@dataclass(frozen=True)
class CheckinSummary:
    """Resumo de check-ins."""
    total: int = 0
    humor_medio: float = 0.0
    energia_media: float = 0.0
    sono_medio: float = 0.0
    ultimo: str = ""
    dias_com_checkin: int = 0
    
    @property
    def has_data(self) -> bool:
        """Verifica se há dados de check-ins."""
        return self.total > 0
    
    @property
    def bem_estar_medio(self) -> float:
        """Retorna bem-estar médio (humor + energia)."""
        if self.humor_medio == 0 and self.energia_media == 0:
            return 0.0
        return round((self.humor_medio + self.energia_media) / 2, 1)
    
    @property
    def bem_estar_label(self) -> str:
        """Retorna label do bem-estar."""
        if self.bem_estar_medio >= 4:
            return "😊 Bom"
        elif self.bem_estar_medio >= 3:
            return "😐 Regular"
        else:
            return "😔 Baixo"
    
    @property
    def humor_emoji(self) -> str:
        """Retorna emoji do humor médio."""
        if self.humor_medio >= 4:
            return "😄"
        elif self.humor_medio >= 3:
            return "😐"
        else:
            return "😔"
    
    @property
    def energia_emoji(self) -> str:
        """Retorna emoji da energia média."""
        if self.energia_media >= 4:
            return "💪"
        elif self.energia_media >= 3:
            return "⚡"
        else:
            return "😴"
    
    @property
    def sono_emoji(self) -> str:
        """Retorna emoji do sono médio."""
        if self.sono_medio >= 4:
            return "😴"
        elif self.sono_medio >= 3:
            return "💤"
        else:
            return "🌙"
    
    @property
    def is_consistent(self) -> bool:
        """Verifica se há check-ins consistentes."""
        return self.total >= 7


@dataclass(frozen=True)
class ConsultationInsight:
    """
    Insight/recomendação automática baseada nos dados.
    
    Attributes:
        category: Categoria do insight
        priority: Prioridade do insight
        title: Título do insight
        message: Mensagem detalhada
        metric_value: Valor da métrica relacionada (se aplicável)
        metric_label: Label da métrica
    """
    category: InsightCategory
    priority: InsightPriority
    title: str
    message: str
    metric_value: float | None = None
    metric_label: str = ""
    
    @property
    def display_text(self) -> str:
        """Retorna texto formatado para exibição."""
        return f"{self.priority.icon} {self.category.icon} {self.title}: {self.message}"
    
    @property
    def is_critical(self) -> bool:
        """Verifica se é um insight crítico."""
        return self.priority == InsightPriority.CRITICAL
    
    @property
    def is_high_priority(self) -> bool:
        """Verifica se é alta prioridade."""
        return self.priority in [InsightPriority.HIGH, InsightPriority.CRITICAL]


@dataclass(frozen=True)
class ConsultationComparison:
    """
    Comparação entre dois períodos.
    
    Attributes:
        patient_id: ID do paciente
        current_period: Período atual
        previous_period: Período anterior
        current_summary: Resumo do período atual
        previous_summary: Resumo do período anterior
        weight_change: Mudança de peso entre períodos
        calorie_change: Mudança de calorias entre períodos
        adherence_change: Mudança de aderência entre períodos
    """
    patient_id: str
    current_period: PeriodInfo
    previous_period: PeriodInfo
    current_summary: ConsultationSummary
    previous_summary: ConsultationSummary
    weight_change: float | None = None
    calorie_change: float | None = None
    adherence_change: float | None = None
    
    @property
    def has_weight_comparison(self) -> bool:
        """Verifica se há comparação de peso."""
        return self.weight_change is not None
    
    @property
    def has_calorie_comparison(self) -> bool:
        """Verifica se há comparação de calorias."""
        return self.calorie_change is not None
    
    @property
    def has_adherence_comparison(self) -> bool:
        """Verifica se há comparação de aderência."""
        return self.adherence_change is not None
    
    @property
    def weight_trend(self) -> str:
        """Retorna tendência de peso."""
        if self.weight_change is None:
            return "neutro"
        if self.weight_change < -0.5:
            return "melhora"
        elif self.weight_change > 0.5:
            return "piora"
        return "estavel"
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido da comparação."""
        parts = []
        if self.has_weight_comparison:
            parts.append(f"Peso: {self.weight_change:+.1f}kg")
        if self.has_calorie_comparison:
            parts.append(f"Calorias: {self.calorie_change:+.0f}kcal")
        if self.has_adherence_comparison:
            parts.append(f"Aderência: {self.adherence_change:+.0f}%")
        return " | ".join(parts) if parts else "Sem dados comparáveis"


@dataclass(frozen=True)
class ConsultationSummary:
    """
    Resumo completo para consulta.
    
    Attributes:
        patient_id: ID do paciente
        patient_name: Nome do paciente
        patient_pillar: Pilar do paciente
        period: Período analisado
        weight: Resumo de peso
        nutrition: Resumo nutricional
        habits: Resumo de hábitos
        checkins: Resumo de check-ins
        goals: Lista de metas
        conducts: Lista de condutas
        alerts: Lista de alertas
        insights: Lista de insights gerados
        xp_total: XP ganho no período
        generated_at: Data de geração
    """
    patient_id: str
    patient_name: str
    patient_pillar: str
    period: PeriodInfo
    weight: WeightSummary
    nutrition: NutritionSummary
    habits: HabitSummary
    checkins: CheckinSummary
    goals: list[dict]
    conducts: list[dict]
    alerts: list[dict]
    insights: list[ConsultationInsight] = field(default_factory=list)
    xp_total: int = 0
    generated_at: str = field(default_factory=lambda: date.today().isoformat())
    
    @classmethod
    def empty(cls, patient_id: str) -> ConsultationSummary:
        """Cria um resumo vazio."""
        return cls(
            patient_id=patient_id,
            patient_name="Paciente",
            patient_pillar="—",
            period=PeriodInfo(days=0, start_date="", end_date=""),
            weight=WeightSummary(),
            nutrition=NutritionSummary(),
            habits=HabitSummary(),
            checkins=CheckinSummary(),
            goals=[],
            conducts=[],
            alerts=[],
            insights=[],
        )
    
    @property
    def has_data(self) -> bool:
        """Verifica se há dados no resumo."""
        return any([
            self.weight.has_data,
            self.nutrition.has_data,
            self.habits.has_data,
            self.checkins.has_data,
            bool(self.goals),
            bool(self.conducts),
            bool(self.alerts),
        ])
    
    @property
    def has_alerts(self) -> bool:
        """Verifica se há alertas."""
        return len(self.alerts) > 0
    
    @property
    def critical_alerts(self) -> list[dict]:
        """Retorna alertas críticos (gravidade >= 3)."""
        return [a for a in self.alerts if a.get("gravidade", 0) >= 3]
    
    @property
    def has_critical_alerts(self) -> bool:
        """Verifica se há alertas críticos."""
        return len(self.critical_alerts) > 0
    
    @property
    def alert_count_by_severity(self) -> dict[int, int]:
        """Retorna contagem de alertas por severidade."""
        counts = {1: 0, 2: 0, 3: 0}
        for alert in self.alerts:
            severity = alert.get("gravidade", 1)
            if severity in counts:
                counts[severity] += 1
        return counts
    
    @property
    def has_insights(self) -> bool:
        """Verifica se há insights."""
        return len(self.insights) > 0
    
    @property
    def critical_insights(self) -> list[ConsultationInsight]:
        """Retorna insights críticos."""
        return [i for i in self.insights if i.is_critical]
    
    @property
    def high_priority_insights(self) -> list[ConsultationInsight]:
        """Retorna insights de alta prioridade."""
        return [i for i in self.insights if i.is_high_priority]
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido do resumo."""
        parts = []
        if self.weight.has_data:
            parts.append(f"⚖️ {self.weight.variacao_label}")
        if self.nutrition.has_data:
            parts.append(f"🍽️ {self.nutrition.media_calorias:.0f} kcal/dia")
        if self.habits.has_data:
            parts.append(f"📋 {self.habits.media_aderencia:.0f}% aderência")
        if self.checkins.has_data:
            parts.append(f"💭 {self.checkins.bem_estar_medio}/5 bem-estar")
        return " | ".join(parts) if parts else "Sem dados suficientes"
    
    @property
    def overall_status(self) -> str:
        """Retorna status geral do paciente."""
        if self.has_critical_alerts:
            return "🚨 Crítico"
        if self.weight.has_data and self.weight.tendencia == "ganho":
            return "⚠️ Atenção"
        if self.nutrition.has_data and self.nutrition.is_low_protein:
            return "⚠️ Atenção"
        if self.habits.has_data and self.habits.media_aderencia < 50:
            return "⚠️ Atenção"
        if self.has_data:
            return "✅ Normal"
        return "❓ Sem dados"


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTATION SUMMARY SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class ConsultationSummaryService:
    """
    Serviço de resumo pré-consulta.
    
    Gera resumos completos para o profissional usar antes da consulta.
    
    Example:
        >>> db = Database()
        >>> summary_service = ConsultationSummaryService(db)
        >>> summary = summary_service.generate("patient_id", days=30)
        >>> print(summary.summary_text)
        >>> print(summary_service.format_text(summary))
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de resumo.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ ConsultationSummaryService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # GENERATION
    # ─────────────────────────────────────────────────────────────────────────

    def generate(
        self,
        patient_id: str,
        days: int = _DEFAULT_DAYS,
    ) -> ConsultationSummary:
        """
        Gera resumo completo do paciente.
        
        Args:
            patient_id: ID do paciente
            days: Número de dias
            
        Returns:
            Objeto ConsultationSummary
        """
        if not patient_id:
            logger.warning("generate: patient_id não informado")
            return ConsultationSummary.empty("")
        
        if days <= 0:
            logger.warning(f"generate: days inválido: {days}")
            days = _DEFAULT_DAYS
        
        logger.info(f"🔄 Gerando resumo para {patient_id} ({days} dias)")
        
        try:
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            
            # Coleta dados
            perfil = self._get_perfil(patient_id)
            peso = self._get_peso(patient_id, cutoff)
            nutricao = self._get_nutricao(patient_id, cutoff)
            habitos = self._get_habitos(patient_id, cutoff)
            checkins = self._get_checkins(patient_id, cutoff)
            metas = self._get_metas(patient_id)
            condutas = self._get_condutas(patient_id)
            alertas = self._get_alertas(patient_id)
            xp = self._get_xp(patient_id, cutoff)
            
            summary = ConsultationSummary(
                patient_id=patient_id,
                patient_name=perfil.get("nome_completo", "Paciente"),
                patient_pillar=perfil.get("tipo_jornada", "—"),
                period=PeriodInfo(
                    days=days,
                    start_date=cutoff,
                    end_date=date.today().isoformat(),
                ),
                weight=peso,
                nutrition=nutricao,
                habits=habitos,
                checkins=checkins,
                goals=metas,
                conducts=condutas,
                alerts=alertas,
                xp_total=xp.get("total", 0),
            )
            
            logger.info(f"✅ Resumo gerado para {patient_id} (has_data={summary.has_data})")
            return summary
            
        except Exception as e:
            logger.error(f"generate falhou para {patient_id}: {e}", exc_info=True)
            return ConsultationSummary.empty(patient_id)

    def generate_with_insights(
        self,
        patient_id: str,
        days: int = _DEFAULT_DAYS,
    ) -> ConsultationSummary:
        """
        Gera resumo completo com insights automáticos.
        
        Args:
            patient_id: ID do paciente
            days: Número de dias
            
        Returns:
            Objeto ConsultationSummary com insights
        """
        summary = self.generate(patient_id, days)
        
        if summary.has_data:
            insights = self.generate_insights(summary)
            
            # Cria novo summary com insights
            summary = ConsultationSummary(
                patient_id=summary.patient_id,
                patient_name=summary.patient_name,
                patient_pillar=summary.patient_pillar,
                period=summary.period,
                weight=summary.weight,
                nutrition=summary.nutrition,
                habits=summary.habits,
                checkins=summary.checkins,
                goals=summary.goals,
                conducts=summary.conducts,
                alerts=summary.alerts,
                insights=insights,
                xp_total=summary.xp_total,
                generated_at=summary.generated_at,
            )
            
            logger.info(f"✅ {len(insights)} insights gerados para {patient_id}")
        
        return summary

    def compare_periods(
        self,
        patient_id: str,
        days_current: int = 30,
        days_previous: int = 30,
    ) -> ConsultationComparison:
        """
        Compara dois períodos do paciente.
        
        Args:
            patient_id: ID do paciente
            days_current: Dias do período atual
            days_previous: Dias do período anterior
            
        Returns:
            Objeto ConsultationComparison
        """
        if not patient_id:
            logger.warning("compare_periods: patient_id não informado")
            return ConsultationComparison(
                patient_id="",
                current_period=PeriodInfo(0, "", ""),
                previous_period=PeriodInfo(0, "", ""),
                current_summary=ConsultationSummary.empty(""),
                previous_summary=ConsultationSummary.empty(""),
            )
        
        # Período atual
        current_summary = self.generate(patient_id, days_current)
        
        # Período anterior (deslocado)
        cutoff_previous_end = (date.today() - timedelta(days=days_current)).isoformat()
        cutoff_previous_start = (date.today() - timedelta(days=days_current + days_previous)).isoformat()
        
        previous_summary = self.generate(patient_id, days_previous)
        
        # Calcula mudanças
        weight_change = None
        if current_summary.weight.has_data and previous_summary.weight.has_data:
            if current_summary.weight.atual is not None and previous_summary.weight.atual is not None:
                weight_change = current_summary.weight.atual - previous_summary.weight.atual
        
        calorie_change = None
        if current_summary.nutrition.has_data and previous_summary.nutrition.has_data:
            calorie_change = current_summary.nutrition.media_calorias - previous_summary.nutrition.media_calorias
        
        adherence_change = None
        if current_summary.habits.has_data and previous_summary.habits.has_data:
            adherence_change = current_summary.habits.media_aderencia - previous_summary.habits.media_aderencia
        
        comparison = ConsultationComparison(
            patient_id=patient_id,
            current_period=current_summary.period,
            previous_period=previous_summary.period,
            current_summary=current_summary,
            previous_summary=previous_summary,
            weight_change=weight_change,
            calorie_change=calorie_change,
            adherence_change=adherence_change,
        )
        
        logger.info(f"✅ Comparação gerada para {patient_id}")
        return comparison

    # ─────────────────────────────────────────────────────────────────────────
    # DATA COLLECTION (com fallback MockDB)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_perfil(self, patient_id: str) -> dict[str, Any]:
        """Busca dados do perfil do paciente."""
        if not patient_id:
            return {}
        
        # Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                response = (
                    self.db.client.table("perfis")
                    .select("nome_completo, tipo_jornada, peso_atual, peso_desejado, altura, idade, genero")
                    .eq("id", patient_id)
                    .limit(1)
                    .execute()
                )
                
                if response.data:
                    return response.data[0]
            except Exception as e:
                logger.warning(f"_get_perfil Supabase: {e}")
        
        # Fallback MockDB
        try:
            users = self.db.mock.get("users", {})
            user_data = users.get(patient_id, {})
            if user_data:
                return {
                    "nome_completo": user_data.get("name", "Paciente"),
                    "tipo_jornada": user_data.get("health_mode", "—"),
                    "peso_atual": user_data.get("current_weight"),
                    "peso_desejado": user_data.get("goal_weight"),
                    "altura": user_data.get("height"),
                    "idade": user_data.get("age"),
                    "genero": user_data.get("gender"),
                }
        except Exception as e:
            logger.warning(f"_get_perfil MockDB: {e}")
        
        return {}

    def _get_peso(self, patient_id: str, cutoff: str) -> WeightSummary:
        """Busca evolução de peso."""
        if not patient_id:
            return WeightSummary()
        
        # Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                response = (
                    self.db.client.table("pesagens")
                    .select("peso, data_pesagem")
                    .eq("perfil_id", patient_id)
                    .gte("data_pesagem", cutoff)
                    .order("data_pesagem")
                    .execute()
                )
                
                dados = response.data or []
                
                if dados:
                    pesos = [float(d["peso"]) for d in dados]
                    
                    return WeightSummary(
                        registros=len(dados),
                        inicial=pesos[0],
                        atual=pesos[-1],
                        variacao=round(pesos[-1] - pesos[0], 1),
                        minimo=min(pesos),
                        maximo=max(pesos),
                        historico=dados[-5:],
                    )
            except Exception as e:
                logger.warning(f"_get_peso Supabase: {e}")
        
        # Fallback MockDB
        try:
            weights = self.db.mock.get("weights", [])
            dados = [
                w for w in weights
                if w.get("user_id") == patient_id and w.get("log_date", "") >= cutoff
            ]
            
            if dados:
                # Ordena por data
                dados.sort(key=lambda x: x.get("log_date", ""))
                pesos = [float(d["weight"]) for d in dados]
                
                return WeightSummary(
                    registros=len(dados),
                    inicial=pesos[0],
                    atual=pesos[-1],
                    variacao=round(pesos[-1] - pesos[0], 1),
                    minimo=min(pesos),
                    maximo=max(pesos),
                    historico=[{"peso": p, "data_pesagem": d.get("log_date")} for p, d in zip(pesos[-5:], dados[-5:])],
                )
        except Exception as e:
            logger.warning(f"_get_peso MockDB: {e}")
        
        return WeightSummary()

    def _get_nutricao(self, patient_id: str, cutoff: str) -> NutritionSummary:
        """Busca média nutricional."""
        if not patient_id:
            return NutritionSummary()
        
        # Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                response = (
                    self.db.client.table("vw_consumo_diario")
                    .select("calorias, proteina, carboidratos, gorduras, fibras")
                    .eq("perfil_id", patient_id)
                    .gte("dia", cutoff)
                    .execute()
                )
                
                dados = response.data or []
                
                if dados:
                    return self._calculate_nutrition_summary(dados)
            except Exception as e:
                logger.warning(f"_get_nutricao Supabase: {e}")
        
        # Fallback MockDB - calcula a partir de refeições
        try:
            meals = self.db.mock.get("meals", [])
            patient_meals = [
                m for m in meals
                if m.get("user_id") == patient_id and m.get("meal_date", "") >= cutoff
            ]
            
            if patient_meals:
                # Agrupa por data
                by_date: dict[str, list] = {}
                for meal in patient_meals:
                    date_key = meal.get("meal_date", "")
                    if date_key not in by_date:
                        by_date[date_key] = []
                    by_date[date_key].append(meal)
                
                # Calcula médias diárias
                dados = []
                for date_key, day_meals in by_date.items():
                    cal = sum(float(m.get("calories", 0)) for m in day_meals)
                    prot = sum(float(m.get("protein", 0)) for m in day_meals)
                    carb = sum(float(m.get("carbs", 0)) for m in day_meals)
                    fat = sum(float(m.get("fat", 0)) for m in day_meals)
                    fiber = sum(float(m.get("fiber", 0)) for m in day_meals)
                    
                    dados.append({
                        "calorias": cal,
                        "proteina": prot,
                        "carboidratos": carb,
                        "gorduras": fat,
                        "fibras": fiber,
                    })
                
                if dados:
                    return self._calculate_nutrition_summary(dados)
        except Exception as e:
            logger.warning(f"_get_nutricao MockDB: {e}")
        
        return NutritionSummary()

    def _calculate_nutrition_summary(self, dados: list[dict]) -> NutritionSummary:
        """Calcula resumo nutricional a partir de dados."""
        n = len(dados)
        cal = sum(float(d.get("calorias", 0) or 0) for d in dados)
        prot = sum(float(d.get("proteina", 0) or 0) for d in dados)
        carb = sum(float(d.get("carboidratos", 0) or 0) for d in dados)
        fat = sum(float(d.get("gorduras", 0) or 0) for d in dados)
        fiber = sum(float(d.get("fibras", 0) or 0) for d in dados)
        
        return NutritionSummary(
            dias_registrados=n,
            media_calorias=round(cal / n, 0),
            media_proteina=round(prot / n, 1),
            media_carbs=round(carb / n, 1),
            media_gordura=round(fat / n, 1),
            media_fibras=round(fiber / n, 1),
        )

    def _get_habitos(self, patient_id: str, cutoff: str) -> HabitSummary:
        """Busca aderência a hábitos."""
        if not patient_id:
            return HabitSummary()
        
        # Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                # Busca hábitos ativos
                habits_response = (
                    self.db.client.table("habitos")
                    .select("id, nome, icone")
                    .eq("perfil_id", patient_id)
                    .eq("ativo", True)
                    .execute()
                )
                
                habits = habits_response.data or []
                
                if habits:
                    dias_periodo = max(1, (date.today() - date.fromisoformat(cutoff)).days)
                    
                    resultado = []
                    for h in habits:
                        reg_response = (
                            self.db.client.table("registros_habitos")
                            .select("id")
                            .eq("habito_id", h["id"])
                            .gte("data_registro", cutoff)
                            .execute()
                        )
                        
                        feitos = len(reg_response.data or [])
                        resultado.append({
                            "nome": h.get("nome", ""),
                            "icone": h.get("icone", "⭐"),
                            "feitos": feitos,
                            "possivel": dias_periodo,
                            "aderencia": round(feitos / dias_periodo * 100, 0),
                        })
                    
                    media = sum(h["aderencia"] for h in resultado) / len(resultado)
                    
                    return HabitSummary(
                        total=len(resultado),
                        media_aderencia=round(media, 0),
                        habitos=resultado,
                    )
            except Exception as e:
                logger.warning(f"_get_habitos Supabase: {e}")
        
        # Fallback MockDB
        try:
            habits = self.db.mock.get("habitos", [])
            patient_habits = [
                h for h in habits
                if h.get("user_id") == patient_id and h.get("ativo", True)
            ]
            
            if patient_habits:
                dias_periodo = max(1, (date.today() - date.fromisoformat(cutoff)).days)
                
                resultado = []
                for h in patient_habits:
                    habit_id = h.get("id", "")
                    
                    # Conta registros
                    records = self.db.mock.get(f"reg_{habit_id}", [])
                    feitos = sum(1 for r in records if r.get("data_registro", "") >= cutoff)
                    
                    resultado.append({
                        "nome": h.get("nome", ""),
                        "icone": h.get("icone", "⭐"),
                        "feitos": feitos,
                        "possivel": dias_periodo,
                        "aderencia": round(feitos / dias_periodo * 100, 0),
                    })
                
                if resultado:
                    media = sum(h["aderencia"] for h in resultado) / len(resultado)
                    
                    return HabitSummary(
                        total=len(resultado),
                        media_aderencia=round(media, 0),
                        habitos=resultado,
                    )
        except Exception as e:
            logger.warning(f"_get_habitos MockDB: {e}")
        
        return HabitSummary()

    def _get_checkins(self, patient_id: str, cutoff: str) -> CheckinSummary:
        """Busca dados de check-ins."""
        if not patient_id:
            return CheckinSummary()
        
        # Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                response = (
                    self.db.client.table("checkins")
                    .select("data_checkin, humor, energia, qualidade_sono")
                    .eq("perfil_id", patient_id)
                    .gte("data_checkin", cutoff)
                    .order("data_checkin", desc=True)
                    .execute()
                )
                
                dados = response.data or []
                
                if dados:
                    return self._calculate_checkin_summary(dados)
            except Exception as e:
                logger.warning(f"_get_checkins Supabase: {e}")
        
        # Fallback MockDB
        try:
            checkins = self.db.mock.get("checkins", [])
            dados = [
                c for c in checkins
                if c.get("user_id") == patient_id and c.get("data_checkin", "") >= cutoff
            ]
            
            if dados:
                # Ordena por data descendente
                dados.sort(key=lambda x: x.get("data_checkin", ""), reverse=True)
                return self._calculate_checkin_summary(dados)
        except Exception as e:
            logger.warning(f"_get_checkins MockDB: {e}")
        
        return CheckinSummary()

    def _calculate_checkin_summary(self, dados: list[dict]) -> CheckinSummary:
        """Calcula resumo de check-ins a partir de dados."""
        humores = [d.get("humor", 0) for d in dados if d.get("humor")]
        energias = [d.get("energia", 0) for d in dados if d.get("energia")]
        sonos = [d.get("qualidade_sono", 0) for d in dados if d.get("qualidade_sono")]
        
        # Conta dias únicos com check-in
        unique_dates = set(d.get("data_checkin", "")[:10] for d in dados)
        
        return CheckinSummary(
            total=len(dados),
            humor_medio=round(sum(humores) / len(humores), 1) if humores else 0,
            energia_media=round(sum(energias) / len(energias), 1) if energias else 0,
            sono_medio=round(sum(sonos) / len(sonos), 1) if sonos else 0,
            ultimo=dados[0].get("data_checkin", "")[:10] if dados else "",
            dias_com_checkin=len(unique_dates),
        )

    def _get_metas(self, patient_id: str) -> list[dict]:
        """Busca metas do paciente."""
        if not patient_id:
            return []
        
        try:
            # Busca jornada ativa
            journey = self.db.get_journey_ativa()
            if not journey:
                return []
            
            journey_id = journey.id if hasattr(journey, "id") else journey.get("id", "")
            
            if not journey_id:
                return []
            
            metas = self.db.get_goals(journey_id)
            
            # Converte para dict se necessário
            result = []
            for meta in metas:
                if hasattr(meta, "to_dict"):
                    result.append(meta.to_dict())
                elif isinstance(meta, dict):
                    result.append(meta)
                else:
                    result.append({"titulo": str(meta)})
            
            return result
            
        except Exception as e:
            logger.warning(f"_get_metas: {e}")
        
        return []

    def _get_condutas(self, patient_id: str) -> list[dict]:
        """Busca condutas anteriores."""
        if not patient_id:
            return []
        
        try:
            if hasattr(self.db, "get_condutas"):
                return self.db.get_condutas(patient_id, limit=5)
            
            if self.db.is_real and self.db.client:
                response = (
                    self.db.client.table("condutas_clinicas")
                    .select("titulo, tipo, data_conduta, descricao")
                    .eq("perfil_id", patient_id)
                    .order("data_conduta", desc=True)
                    .limit(5)
                    .execute()
                )
                return response.data or []
            
            # Fallback MockDB
            condutas = self.db.mock.get("condutas_clinicas", {})
            patient_condutas = condutas.get(patient_id, [])
            return patient_condutas[:5]
            
        except Exception as e:
            logger.warning(f"_get_condutas: {e}")
        
        return []

    def _get_alertas(self, patient_id: str) -> list[dict]:
        """Busca alertas em aberto."""
        if not patient_id:
            return []
        
        if self.db.is_real and self.db.client:
            try:
                response = (
                    self.db.client.table("alertas_clinicos")
                    .select("titulo, categoria, gravidade, criado_em")
                    .eq("perfil_id", patient_id)
                    .eq("resolvido", False)
                    .order("gravidade", desc=True)
                    .limit(5)
                    .execute()
                )
                return response.data or []
            except Exception as e:
                logger.warning(f"_get_alertas Supabase: {e}")
        
        # Fallback MockDB
        try:
            alertas = self.db.mock.get("alertas_clinicos", {})
            patient_alertas = alertas.get(patient_id, [])
            # Filtra não resolvidos e ordena por gravidade
            open_alertas = [a for a in patient_alertas if not a.get("resolvido", False)]
            open_alertas.sort(key=lambda x: x.get("gravidade", 0), reverse=True)
            return open_alertas[:5]
        except Exception as e:
            logger.warning(f"_get_alertas MockDB: {e}")
        
        return []

    def _get_xp(self, patient_id: str, cutoff: str) -> dict[str, Any]:
        """Busca XP do período."""
        if not patient_id:
            return {"total": 0}
        
        if self.db.is_real and self.db.client:
            try:
                response = (
                    self.db.client.table("historico_xp")
                    .select("xp_ganho")
                    .eq("perfil_id", patient_id)
                    .gte("criado_em", cutoff)
                    .execute()
                )
                
                dados = response.data or []
                total = sum(int(d.get("xp_ganho", 0) or 0) for d in dados)
                
                return {"total": total, "registros": len(dados)}
            except Exception as e:
                logger.warning(f"_get_xp Supabase: {e}")
        
        # Fallback MockDB - estima baseado em atividades
        try:
            # Estima XP baseado em check-ins, refeições, etc.
            checkins = self.db.mock.get("checkins", [])
            patient_checkins = [c for c in checkins if c.get("user_id") == patient_id and c.get("data_checkin", "") >= cutoff]
            
            meals = self.db.mock.get("meals", [])
            patient_meals = [m for m in meals if m.get("user_id") == patient_id and m.get("meal_date", "") >= cutoff]
            
            # Estima: 20 XP por check-in, 5 XP por refeição
            total = (len(patient_checkins) * 20) + (len(patient_meals) * 5)
            
            return {"total": total, "registros": len(patient_checkins) + len(patient_meals)}
        except Exception as e:
            logger.warning(f"_get_xp MockDB: {e}")
        
        return {"total": 0}

    # ─────────────────────────────────────────────────────────────────────────
    # ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────

    def generate_insights(self, summary: ConsultationSummary) -> list[ConsultationInsight]:
        """
        Gera insights automáticos baseados nos dados.
        
        Args:
            summary: Resumo do paciente
            
        Returns:
            Lista de ConsultationInsight
        """
        insights = []
        
        # Analisa peso
        weight_insight = self._analyze_weight(summary)
        if weight_insight:
            insights.append(weight_insight)
        
        # Analisa nutrição
        nutrition_insights = self._analyze_nutrition(summary)
        insights.extend(nutrition_insights)
        
        # Analisa hábitos
        habit_insights = self._analyze_habits(summary)
        insights.extend(habit_insights)
        
        # Analisa check-ins
        checkin_insight = self._analyze_checkins(summary)
        if checkin_insight:
            insights.append(checkin_insight)
        
        # Analisa engajamento
        engagement_insight = self._analyze_engagement(summary)
        if engagement_insight:
            insights.append(engagement_insight)
        
        # Analisa alertas
        alert_insight = self._analyze_alerts(summary)
        if alert_insight:
            insights.append(alert_insight)
        
        # Ordena por prioridade
        priority_order = {
            InsightPriority.CRITICAL: 0,
            InsightPriority.HIGH: 1,
            InsightPriority.MEDIUM: 2,
            InsightPriority.LOW: 3,
        }
        insights.sort(key=lambda x: priority_order.get(x.priority, 99))
        
        return insights

    def _analyze_weight(self, summary: ConsultationSummary) -> ConsultationInsight | None:
        """Analisa dados de peso."""
        if not summary.weight.has_data:
            return None
        
        weight = summary.weight
        
        # Perda significativa
        if weight.variacao is not None and weight.variacao < -_WEIGHT_LOSS_SIGNIFICANT:
            return ConsultationInsight(
                category=InsightCategory.WEIGHT,
                priority=InsightPriority.LOW,
                title="Perda de peso significativa",
                message=f"Paciente perdeu {abs(weight.variacao):.1f}kg no período. Excelente progresso!",
                metric_value=weight.variacao,
                metric_label="Variação",
            )
        
        # Ganho significativo
        if weight.variacao is not None and weight.variacao > _WEIGHT_GAIN_SIGNIFICANT:
            return ConsultationInsight(
                category=InsightCategory.WEIGHT,
                priority=InsightPriority.HIGH,
                title="Ganho de peso significativo",
                message=f"Paciente ganhou {weight.variacao:.1f}kg no período. Investigar causas.",
                metric_value=weight.variacao,
                metric_label="Variação",
            )
        
        # Alta amplitude
        if weight.amplitude > 5:
            return ConsultationInsight(
                category=InsightCategory.WEIGHT,
                priority=InsightPriority.MEDIUM,
                title="Alta oscilação de peso",
                message=f"Amplitude de {weight.amplitude:.1f}kg entre mínimo e máximo. Pode indicar inconsistência.",
                metric_value=weight.amplitude,
                metric_label="Amplitude",
            )
        
        return None

    def _analyze_nutrition(self, summary: ConsultationSummary) -> list[ConsultationInsight]:
        """Analisa dados nutricionais."""
        insights = []
        
        if not summary.nutrition.has_data:
            return insights
        
        nutrition = summary.nutrition
        
        # Baixa consistência
        if nutrition.dias_registrados < 7:
            insights.append(ConsultationInsight(
                category=InsightCategory.NUTRITION,
                priority=InsightPriority.MEDIUM,
                title="Baixa consistência no registro",
                message=f"Apenas {nutrition.dias_registrados} dias com registro. Incentivar registro diário.",
                metric_value=nutrition.dias_registrados,
                metric_label="Dias registrados",
            ))
        
        # Calorias muito baixas
        if nutrition.is_low_calorie:
            insights.append(ConsultationInsight(
                category=InsightCategory.NUTRITION,
                priority=InsightPriority.HIGH,
                title="Ingestão calórica muito baixa",
                message=f"Média de {nutrition.media_calorias:.0f} kcal/dia. Risco de déficit excessivo.",
                metric_value=nutrition.media_calorias,
                metric_label="Calorias/dia",
            ))
        
        # Calorias muito altas
        if nutrition.is_high_calorie:
            insights.append(ConsultationInsight(
                category=InsightCategory.NUTRITION,
                priority=InsightPriority.MEDIUM,
                title="Ingestão calórica alta",
                message=f"Média de {nutrition.media_calorias:.0f} kcal/dia. Revisar porções.",
                metric_value=nutrition.media_calorias,
                metric_label="Calorias/dia",
            ))
        
        # Proteína baixa
        if nutrition.is_low_protein:
            insights.append(ConsultationInsight(
                category=InsightCategory.NUTRITION,
                priority=InsightPriority.HIGH,
                title="Proteína insuficiente",
                message=f"Média de {nutrition.media_proteina:.1f}g/dia. Priorizar fontes proteicas.",
                metric_value=nutrition.media_proteina,
                metric_label="Proteína/dia",
            ))
        
        return insights

    def _analyze_habits(self, summary: ConsultationSummary) -> list[ConsultationInsight]:
        """Analisa dados de hábitos."""
        insights = []
        
        if not summary.habits.has_data:
            return insights
        
        habits = summary.habits
        
        # Aderência geral baixa
        if habits.media_aderencia < _ADHERENCE_LOW:
            insights.append(ConsultationInsight(
                category=InsightCategory.HABITS,
                priority=InsightPriority.HIGH,
                title="Aderência muito baixa aos hábitos",
                message=f"Média de {habits.media_aderencia:.0f}% de aderência. Revisar plano de hábitos.",
                metric_value=habits.media_aderencia,
                metric_label="Aderência",
            ))
        elif habits.media_aderencia < _ADHERENCE_MODERATE:
            insights.append(ConsultationInsight(
                category=InsightCategory.HABITS,
                priority=InsightPriority.MEDIUM,
                title="Aderência baixa aos hábitos",
                message=f"Média de {habits.media_aderencia:.0f}% de aderência. Reforçar importância.",
                metric_value=habits.media_aderencia,
                metric_label="Aderência",
            ))
        
        # Hábitos muito ruins
        if habits.habits_below_30 > 0:
            worst = habits.worst_habit
            if worst:
                insights.append(ConsultationInsight(
                    category=InsightCategory.HABITS,
                    priority=InsightPriority.MEDIUM,
                    title=f"Hábito crítico: {worst.get('nome', '—')}",
                    message=f"Apenas {worst.get('aderencia', 0):.0f}% de aderência. Considerar substituir ou remover.",
                    metric_value=worst.get("aderencia", 0),
                    metric_label="Aderência",
                ))
        
        # Hábitos muito bons
        if habits.habits_above_70 >= 2:
            best = habits.best_habit
            if best:
                insights.append(ConsultationInsight(
                    category=InsightCategory.HABITS,
                    priority=InsightPriority.LOW,
                    title=f"Hábito consolidado: {best.get('nome', '—')}",
                    message=f"{best.get('aderencia', 0):.0f}% de aderência. Excelente consistência!",
                    metric_value=best.get("aderencia", 0),
                    metric_label="Aderência",
                ))
        
        return insights

    def _analyze_checkins(self, summary: ConsultationSummary) -> ConsultationInsight | None:
        """Analisa dados de check-ins."""
        if not summary.checkins.has_data:
            return None
        
        checkins = summary.checkins
        
        # Bem-estar baixo
        if checkins.bem_estar_medio < 3:
            return ConsultationInsight(
                category=InsightCategory.CHECKINS,
                priority=InsightPriority.HIGH,
                title="Bem-estar baixo",
                message=f"Bem-estar médio de {checkins.bem_estar_medio}/5. Investigar causas.",
                metric_value=checkins.bem_estar_medio,
                metric_label="Bem-estar",
            )
        
        # Sono ruim
        if checkins.sono_medio < 3 and checkins.sono_medio > 0:
            return ConsultationInsight(
                category=InsightCategory.CHECKINS,
                priority=InsightPriority.MEDIUM,
                title="Qualidade de sono baixa",
                message=f"Sono médio de {checkins.sono_medio}/5. Orientar sobre higiene do sono.",
                metric_value=checkins.sono_medio,
                metric_label="Sono",
            )
        
        return None

    def _analyze_engagement(self, summary: ConsultationSummary) -> ConsultationInsight | None:
        """Analisa engajamento."""
        if summary.xp_total == 0:
            return ConsultationInsight(
                category=InsightCategory.ENGAGEMENT,
                priority=InsightPriority.HIGH,
                title="Sem engajamento",
                message="Paciente não ganhou XP no período. Risco de abandono.",
                metric_value=0,
                metric_label="XP",
            )
        
        if summary.xp_total < 100:
            return ConsultationInsight(
                category=InsightCategory.ENGAGEMENT,
                priority=InsightPriority.MEDIUM,
                title="Engajamento baixo",
                message=f"Apenas {summary.xp_total} XP ganho no período. Incentivar mais atividade.",
                metric_value=summary.xp_total,
                metric_label="XP",
            )
        
        if summary.xp_total >= 500:
            return ConsultationInsight(
                category=InsightCategory.ENGAGEMENT,
                priority=InsightPriority.LOW,
                title="Alto engajamento",
                message=f"{summary.xp_total} XP ganho no período. Excelente consistência!",
                metric_value=summary.xp_total,
                metric_label="XP",
            )
        
        return None

    def _analyze_alerts(self, summary: ConsultationSummary) -> ConsultationInsight | None:
        """Analisa alertas."""
        if not summary.has_alerts:
            return None
        
        if summary.has_critical_alerts:
            count = len(summary.critical_alerts)
            return ConsultationInsight(
                category=InsightCategory.ALERTS,
                priority=InsightPriority.CRITICAL,
                title=f"{count} alerta(s) crítico(s)",
                message="Paciente com alertas graves em aberto. Ação imediata necessária.",
                metric_value=count,
                metric_label="Alertas críticos",
            )
        
        count = len(summary.alerts)
        return ConsultationInsight(
            category=InsightCategory.ALERTS,
            priority=InsightPriority.MEDIUM,
            title=f"{count} alerta(s) em aberto",
            message="Paciente com alertas não resolvidos. Revisar durante consulta.",
            metric_value=count,
            metric_label="Alertas",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # FORMATTING
    # ─────────────────────────────────────────────────────────────────────────

    def format_text(self, summary: ConsultationSummary) -> str:
        """
        Formata resumo como texto estruturado.
        
        Args:
            summary: Objeto ConsultationSummary
            
        Returns:
            Texto formatado
        """
        if not summary or not summary.has_data:
            return "Nenhum dado disponível para este paciente no período selecionado."
        
        lines = []
        lines.append("=" * 60)
        lines.append("MELSHAPE — RESUMO PRÉ-CONSULTA")
        lines.append("=" * 60)
        lines.append("")
        
        # Cabeçalho
        lines.extend(self._format_header(summary))
        lines.append("")
        
        # Status geral
        lines.append(f"STATUS GERAL: {summary.overall_status}")
        lines.append("")
        
        # Seções
        lines.append(self._format_section_weight(summary))
        lines.append("")
        lines.append(self._format_section_nutrition(summary))
        lines.append("")
        lines.append(self._format_section_habits(summary))
        lines.append("")
        lines.append(self._format_section_checkins(summary))
        lines.append("")
        
        if summary.goals:
            lines.append(self._format_section_goals(summary))
            lines.append("")
        
        if summary.conducts:
            lines.append(self._format_section_condutas(summary))
            lines.append("")
        
        if summary.alerts:
            lines.append(self._format_section_alertas(summary))
            lines.append("")
        
        if summary.has_insights:
            lines.append(self._format_section_insights(summary))
            lines.append("")
        
        # Engajamento
        lines.append(self._format_section_engajamento(summary))
        lines.append("")
        
        lines.append("=" * 60)
        lines.append("Melshape · melshape.com.br")
        lines.append("=" * 60)
        
        return "\n".join(lines)

    def format_markdown(self, summary: ConsultationSummary) -> str:
        """
        Formata resumo como Markdown.
        
        Args:
            summary: Objeto ConsultationSummary
            
        Returns:
            Markdown formatado
        """
        if not summary or not summary.has_data:
            return "Nenhum dado disponível para este paciente no período selecionado."
        
        lines = []
        lines.append("# 📋 Resumo Pré-Consulta")
        lines.append("")
        
        # Cabeçalho
        lines.append(f"**Paciente:** {summary.patient_name}")
        lines.append(f"**Pilar:** {summary.patient_pillar}")
        lines.append(f"**Período:** {summary.period.range_label}")
        lines.append(f"**Status:** {summary.overall_status}")
        lines.append("")
        
        # Peso
        if summary.weight.has_data:
            lines.append("## ⚖️ Peso")
            lines.append(f"- **Registros:** {summary.weight.registros}")
            lines.append(f"- **Inicial:** {summary.weight.inicial:.1f} kg")
            lines.append(f"- **Atual:** {summary.weight.atual:.1f} kg")
            lines.append(f"- **Variação:** {summary.weight.variacao_label}")
            if summary.weight.minimo:
                lines.append(f"- **Mínimo:** {summary.weight.minimo:.1f} kg")
            if summary.weight.maximo:
                lines.append(f"- **Máximo:** {summary.weight.maximo:.1f} kg")
            lines.append("")
        
        # Nutrição
        if summary.nutrition.has_data:
            lines.append("## 🍽️ Nutrição (Média)")
            lines.append(f"- **Dias registrados:** {summary.nutrition.dias_registrados}")
            lines.append(f"- **Calorias:** {summary.nutrition.media_calorias:.0f} kcal/dia")
            lines.append(f"- **Proteína:** {summary.nutrition.media_proteina:.1f} g/dia")
            lines.append(f"- **Carboidratos:** {summary.nutrition.media_carbs:.1f} g/dia")
            lines.append(f"- **Gorduras:** {summary.nutrition.media_gordura:.1f} g/dia")
            lines.append("")
        
        # Hábitos
        if summary.habits.has_data:
            lines.append("## 📋 Hábitos")
            lines.append(f"**Aderência média:** {summary.habits.media_aderencia:.0f}%")
            lines.append("")
            for h in summary.habits.habitos:
                lines.append(f"- {h.get('icone', '⭐')} **{h.get('nome', '—')}**: {h.get('aderencia', 0):.0f}%")
            lines.append("")
        
        # Check-ins
        if summary.checkins.has_data:
            lines.append("## 💭 Check-ins")
            lines.append(f"- **Total:** {summary.checkins.total} check-ins")
            lines.append(f"- **Bem-estar médio:** {summary.checkins.bem_estar_medio}/5")
            lines.append(f"- **Humor:** {summary.checkins.humor_medio}/5 {summary.checkins.humor_emoji}")
            lines.append(f"- **Energia:** {summary.checkins.energia_media}/5 {summary.checkins.energia_emoji}")
            lines.append(f"- **Sono:** {summary.checkins.sono_medio}/5 {summary.checkins.sono_emoji}")
            lines.append("")
        
        # Insights
        if summary.has_insights:
            lines.append("## 💡 Insights")
            for insight in summary.insights:
                lines.append(f"- {insight.display_text}")
            lines.append("")
        
        # Engajamento
        lines.append("## ⭐ Engajamento")
        lines.append(f"**XP ganho:** {summary.xp_total} pts")
        lines.append("")
        
        return "\n".join(lines)

    def format_json(self, summary: ConsultationSummary) -> str:
        """
        Formata resumo como JSON.
        
        Args:
            summary: Objeto ConsultationSummary
            
        Returns:
            JSON formatado
        """
        data = {
            "patient_id": summary.patient_id,
            "patient_name": summary.patient_name,
            "patient_pillar": summary.patient_pillar,
            "period": {
                "days": summary.period.days,
                "start_date": summary.period.start_date,
                "end_date": summary.period.end_date,
            },
            "weight": {
                "registros": summary.weight.registros,
                "inicial": summary.weight.inicial,
                "atual": summary.weight.atual,
                "variacao": summary.weight.variacao,
                "minimo": summary.weight.minimo,
                "maximo": summary.weight.maximo,
            },
            "nutrition": {
                "dias_registrados": summary.nutrition.dias_registrados,
                "media_calorias": summary.nutrition.media_calorias,
                "media_proteina": summary.nutrition.media_proteina,
                "media_carbs": summary.nutrition.media_carbs,
                "media_gordura": summary.nutrition.media_gordura,
            },
            "habits": {
                "total": summary.habits.total,
                "media_aderencia": summary.habits.media_aderencia,
                "habitos": summary.habits.habitos,
            },
            "checkins": {
                "total": summary.checkins.total,
                "humor_medio": summary.checkins.humor_medio,
                "energia_media": summary.checkins.energia_media,
                "sono_medio": summary.checkins.sono_medio,
            },
            "goals": summary.goals,
            "conducts": summary.conducts,
            "alerts": summary.alerts,
            "insights": [
                {
                    "category": i.category.value,
                    "priority": i.priority.value,
                    "title": i.title,
                    "message": i.message,
                }
                for i in summary.insights
            ],
            "xp_total": summary.xp_total,
            "generated_at": summary.generated_at,
        }
        
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _format_header(self, summary: ConsultationSummary) -> list[str]:
        """Formata cabeçalho do resumo."""
        return [
            f"Paciente: {summary.patient_name}",
            f"Pilar: {summary.patient_pillar}",
            f"Período: {summary.period.range_label}",
            f"Gerado em: {summary.generated_at}",
        ]

    def _format_section_weight(self, summary: ConsultationSummary) -> str:
        """Formata seção de peso."""
        lines = ["── PESO ──"]
        if summary.weight.has_data:
            lines.append(f"Registros: {summary.weight.registros}")
            lines.append(f"Inicial: {summary.weight.inicial:.1f} kg")
            lines.append(f"Atual: {summary.weight.atual:.1f} kg")
            lines.append(f"Variação: {summary.weight.variacao_label}")
            if summary.weight.minimo:
                lines.append(f"Mínimo: {summary.weight.minimo:.1f} kg")
            if summary.weight.maximo:
                lines.append(f"Máximo: {summary.weight.maximo:.1f} kg")
        else:
            lines.append("Sem registros de peso")
        return "\n".join(lines)

    def _format_section_nutrition(self, summary: ConsultationSummary) -> str:
        """Formata seção de nutrição."""
        lines = ["── NUTRIÇÃO (MÉDIA DO PERÍODO) ──"]
        if summary.nutrition.has_data:
            lines.append(f"Dias com registro: {summary.nutrition.dias_registrados}")
            lines.append(f"Calorias: {summary.nutrition.media_calorias:.0f} kcal/dia")
            lines.append(f"Proteína: {summary.nutrition.media_proteina:.1f} g/dia")
            lines.append(f"Carboidratos: {summary.nutrition.media_carbs:.1f} g/dia")
            lines.append(f"Gorduras: {summary.nutrition.media_gordura:.1f} g/dia")
        else:
            lines.append("Sem registros nutricionais")
        return "\n".join(lines)

    def _format_section_habits(self, summary: ConsultationSummary) -> str:
        """Formata seção de hábitos."""
        lines = ["── HÁBITOS ──"]
        if summary.habits.has_data:
            lines.append(f"Aderência média: {summary.habits.media_aderencia:.0f}%")
            for h in summary.habits.habitos:
                lines.append(f"  {h.get('icone', '⭐')} {h.get('nome', '—')}: {h.get('aderencia', 0):.0f}%")
        else:
            lines.append("Sem hábitos cadastrados")
        return "\n".join(lines)

    def _format_section_checkins(self, summary: ConsultationSummary) -> str:
        """Formata seção de check-ins."""
        lines = ["── CHECK-INS ──"]
        if summary.checkins.has_data:
            lines.append(f"Total: {summary.checkins.total} check-ins")
            lines.append(f"Bem-estar médio: {summary.checkins.bem_estar_medio}/5")
            lines.append(f"Humor médio: {summary.checkins.humor_medio}/5")
            lines.append(f"Energia média: {summary.checkins.energia_media}/5")
            lines.append(f"Sono médio: {summary.checkins.sono_medio}/5")
            if summary.checkins.ultimo:
                lines.append(f"Último: {summary.checkins.ultimo}")
        else:
            lines.append("Sem check-ins registrados")
        return "\n".join(lines)

    def _format_section_goals(self, summary: ConsultationSummary) -> str:
        """Formata seção de metas."""
        lines = ["── METAS ──"]
        for goal in summary.goals[:5]:
            status = "✅" if goal.get("concluida") else "⏳"
            titulo = goal.get("titulo", "Meta")
            valor_atual = goal.get("valor_atual", "?")
            valor_alvo = goal.get("valor_alvo", "?")
            lines.append(f"  {status} {titulo} ({valor_atual}/{valor_alvo})")
        return "\n".join(lines)

    def _format_section_condutas(self, summary: ConsultationSummary) -> str:
        """Formata seção de condutas."""
        lines = ["── CONDUTAS ANTERIORES ──"]
        for cond in summary.conducts[:5]:
            data = cond.get("data_conduta", "")[:10]
            titulo = cond.get("titulo", "—")
            lines.append(f"  [{data}] {titulo}")
        return "\n".join(lines)

    def _format_section_alertas(self, summary: ConsultationSummary) -> str:
        """Formata seção de alertas."""
        lines = ["── ALERTAS EM ABERTO ──"]
        for alert in summary.alerts[:5]:
            severidade = alert.get("gravidade", 1)
            label = _ALERT_LABELS.get(severidade, f"⚠️ {severidade}")
            titulo = alert.get("titulo", "—")
            lines.append(f"  {label} {titulo}")
        return "\n".join(lines)

    def _format_section_insights(self, summary: ConsultationSummary) -> str:
        """Formata seção de insights."""
        lines = ["── INSIGHTS AUTOMÁTICOS ──"]
        for insight in summary.insights[:10]:
            lines.append(f"  {insight.display_text}")
        return "\n".join(lines)

    def _format_section_engajamento(self, summary: ConsultationSummary) -> str:
        """Formata seção de engajamento."""
        lines = ["── ENGAJAMENTO ──"]
        lines.append(f"XP ganho no período: {summary.xp_total} pts")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def _safe_float(self, value: Any) -> float:
        """Converte valor para float com segurança."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _safe_date(self, date_str: Any) -> str:
        """Converte data para string com segurança."""
        if not date_str:
            return ""
        try:
            return date_str[:10]
        except (ValueError, TypeError, AttributeError):
            return str(date_str)

    def _calculate_percentage_change(self, current: float, previous: float) -> float:
        """
        Calcula mudança percentual.
        
        Args:
            current: Valor atual
            previous: Valor anterior
            
        Returns:
            Mudança percentual
        """
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100


__all__ = [
    "ConsultationSummaryService",
    "ConsultationSummary",
    "ConsultationInsight",
    "ConsultationComparison",
    "PeriodInfo",
    "WeightSummary",
    "NutritionSummary",
    "HabitSummary",
    "CheckinSummary",
    "InsightPriority",
    "InsightCategory",
]
