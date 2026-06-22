"""
Melshape — Nutrition Alerts.

Alertas clínicos nutricionais para o paciente.
Importado por NutritionService.

Alertas disponíveis:
  - calorie_alert: calorias vs meta diária
  - protein_alert: proteína vs meta
  - glp1_low_calorie_alert: <900kcal por 3+ dias (GLP-1)
  - bariatric_volume_alert: volume excede fase bariátrica
  - protein_two_day_alert: proteína <50% por 2 dias seguidos
  - nutrient_score: score 0-100 de um alimento
  - meal_timing_alert: refeições fora do horário adequado
  - hydration_alert: hidratação insuficiente

Princípios:
- Alertas acionáveis: sempre incluem sugestão de ação
- Contexto clínico: adaptado ao modo de saúde do paciente
- Nunca punir: alertas são informativos, não críticos
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    NutritionAlerts
    ├── Alert Generators
    │   ├── calorie_alert(calories, goal) -> NutritionAlert | None
    │   ├── protein_alert(protein, goal) -> NutritionAlert | None
    │   ├── glp1_low_calorie_alert(daily_summary_fn) -> NutritionAlert | None
    │   ├── bariatric_volume_alert(volume_ml, phase) -> NutritionAlert | None
    │   ├── protein_two_day_alert(daily_summary_fn, prot_goal) -> NutritionAlert | None
    │   ├── meal_timing_alert(meals) -> NutritionAlert | None
    │   ├── hydration_alert(hydration, goal) -> NutritionAlert | None
    │   ├── fiber_alert(fiber, goal) -> NutritionAlert | None
    │   └── meal_balance_alert(meal) -> NutritionAlert | None
    ├── Nutrient Scoring
    │   └── nutrient_score(food) -> int
    ├── Alert Aggregation
    │   ├── get_alerts_for_user(user) -> list[NutritionAlert]
    │   └── get_critical_alerts_for_user(user) -> list[NutritionAlert]
    └── Utilities
        ├── _create_alert(type, severity, message, action) -> NutritionAlert
        └── _safe_float(value) -> float
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

import config

logger = logging.getLogger("Melshape.NutritionAlerts")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds calóricos
_CALORIE_SAFE_MIN: int = config.MIN_CALORIES_SAFE
_CALORIE_WARNING_PCT: float = config.ALERT_PCT_WARNING

# Thresholds de proteína
_PROTEIN_GOOD_PCT: float = 0.8
_PROTEIN_WARNING_PCT: float = 0.5
_PROTEIN_CRITICAL_PCT: float = 0.3

# GLP-1
_GLP1_LOW_KCAL_THRESHOLD: int = config.GLP1_LOW_KCAL_THRESHOLD
_GLP1_LOW_KCAL_DAYS: int = config.GLP1_LOW_KCAL_DAYS

# Bariátrica
_BARIATRIC_VOLUME_PCT: float = 0.9

# Hidratação
_HYDRATION_GOOD_PCT: float = 0.8
_HYDRATION_WARNING_PCT: float = 0.6
_HYDRATION_CRITICAL_PCT: float = 0.3

# Fibras
_FIBER_MIN_GOAL: float = 25.0
_FIBER_GOOD_PCT: float = 0.8
_FIBER_WARNING_PCT: float = 0.5

# Refeições
_MIN_MEALS_PER_DAY: int = 3
_MAX_HOURS_WITHOUT_MEAL: int = 6

# Horários ideais para refeições
_IDEAL_MEAL_TIMES: dict[str, tuple[int, int]] = {
    "cafe_manha": (6, 10),
    "almoco": (11, 14),
    "jantar": (18, 21),
    "lanche": (9, 11, 15, 17),
}


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    """Severidade do alerta nutricional."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "error"
    
    @property
    def icon(self) -> str:
        """Retorna ícone da severidade."""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨",
        }
        return icons.get(self.value, "ℹ️")
    
    @property
    def label(self) -> str:
        """Retorna label da severidade."""
        labels = {
            "info": "Informativo",
            "warning": "Atenção",
            "error": "Crítico",
        }
        return labels.get(self.value, "Info")


class AlertCategory(str, Enum):
    """Categoria do alerta nutricional."""
    CALORIE = "calorie"
    PROTEIN = "protein"
    HYDRATION = "hydration"
    FIBER = "fiber"
    VOLUME = "volume"
    TIMING = "timing"
    BALANCE = "balance"
    GLP1 = "glp1"
    BARIATRIC = "bariatric"


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NutritionAlert:
    """
    Modelo de alerta nutricional.
    
    Attributes:
        category: Categoria do alerta
        severity: Severidade do alerta
        title: Título do alerta
        message: Mensagem detalhada
        action: Ação sugerida
        metric_value: Valor da métrica (opcional)
        metric_label: Label da métrica (opcional)
        created_at: Timestamp de criação
    """
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    action: str = ""
    metric_value: float | None = None
    metric_label: str = ""
    created_at: str = field(default_factory=lambda: __import__("datetime").datetime.now().isoformat())
    
    @property
    def icon(self) -> str:
        """Retorna ícone do alerta baseado na categoria."""
        icons = {
            AlertCategory.CALORIE: "🔥",
            AlertCategory.PROTEIN: "🥩",
            AlertCategory.HYDRATION: "💧",
            AlertCategory.FIBER: "🌾",
            AlertCategory.VOLUME: "🥄",
            AlertCategory.TIMING: "⏰",
            AlertCategory.BALANCE: "⚖️",
            AlertCategory.GLP1: "💉",
            AlertCategory.BARIATRIC: "🔪",
        }
        return icons.get(self.category, "📋")
    
    @property
    def display_text(self) -> str:
        """Retorna texto formatado para exibição."""
        return f"{self.severity.icon} {self.icon} {self.title}: {self.message}"
    
    @property
    def is_critical(self) -> bool:
        """Verifica se é um alerta crítico."""
        return self.severity == AlertSeverity.CRITICAL
    
    @property
    def is_warning(self) -> bool:
        """Verifica se é um alerta de atenção."""
        return self.severity == AlertSeverity.WARNING
    
    @property
    def is_info(self) -> bool:
        """Verifica se é um alerta informativo."""
        return self.severity == AlertSeverity.INFO


# ─────────────────────────────────────────────────────────────────────────────
# ALERT GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def calorie_alert(calories: float, goal: float) -> NutritionAlert | None:
    """
    Alerta de calorias vs meta diária.
    
    Args:
        calories: Calorias consumidas
        goal: Meta calórica
    
    Returns:
        NutritionAlert ou None
    """
    if goal <= 0 or calories <= 0:
        return None

    pct = calories / goal

    # Crítico: abaixo do mínimo seguro
    if calories < _CALORIE_SAFE_MIN:
        return NutritionAlert(
            category=AlertCategory.CALORIE,
            severity=AlertSeverity.CRITICAL,
            title="🚨 Consumo calórico muito baixo",
            message=f"Você consumiu {calories:.0f} kcal. "
                    f"Valor abaixo do mínimo seguro ({_CALORIE_SAFE_MIN} kcal).",
            action="Considere fazer uma refeição nutritiva agora.",
            metric_value=calories,
            metric_label="Calorias consumidas",
        )

    # Meta atingida
    if pct >= 1.0:
        return NutritionAlert(
            category=AlertCategory.CALORIE,
            severity=AlertSeverity.INFO,
            title="🎯 Meta calórica atingida",
            message=f"Você consumiu {calories:.0f} kcal — "
                    f"atingiu sua meta calórica diária.",
            action="Foque na qualidade das próximas refeições.",
            metric_value=calories,
            metric_label="Calorias consumidas",
        )

    # Próximo da meta
    if pct >= _CALORIE_WARNING_PCT:
        remaining = goal - calories
        return NutritionAlert(
            category=AlertCategory.CALORIE,
            severity=AlertSeverity.INFO,
            title="⚡ Quase lá!",
            message=f"Você consumiu {calories:.0f} kcal. "
                    f"Faltam {remaining:.0f} kcal para sua meta.",
            action="Continue no ritmo — qualidade importa.",
            metric_value=remaining,
            metric_label="Calorias restantes",
        )

    return None


def protein_alert(protein: float, goal: float) -> NutritionAlert | None:
    """
    Alerta de proteína vs meta.
    
    Args:
        protein: Proteína consumida (g)
        goal: Meta de proteína (g)
    
    Returns:
        NutritionAlert ou None
    """
    if goal <= 0 or protein <= 0:
        return None

    pct = protein / goal

    # Crítico: muito baixo
    if pct < _PROTEIN_CRITICAL_PCT:
        return NutritionAlert(
            category=AlertCategory.PROTEIN,
            severity=AlertSeverity.CRITICAL,
            title="🥩 Proteína muito baixa",
            message=f"Você consumiu {protein:.0f}g de {goal:.0f}g "
                    f"({pct * 100:.0f}% da meta).",
            action="Priorize fontes proteicas na próxima refeição — ovos, frango, whey.",
            metric_value=protein,
            metric_label="Proteína consumida",
        )

    # Atenção: abaixo de 50%
    if pct < _PROTEIN_WARNING_PCT:
        return NutritionAlert(
            category=AlertCategory.PROTEIN,
            severity=AlertSeverity.WARNING,
            title="🥩 Proteína abaixo da meta",
            message=f"Você consumiu {protein:.0f}g de {goal:.0f}g "
                    f"({pct * 100:.0f}% da meta).",
            action="Adicione uma fonte proteica na próxima refeição.",
            metric_value=protein,
            metric_label="Proteína consumida",
        )

    # Excelente
    if pct >= _PROTEIN_GOOD_PCT:
        return NutritionAlert(
            category=AlertCategory.PROTEIN,
            severity=AlertSeverity.INFO,
            title="🥩 Proteína excelente!",
            message=f"Você consumiu {protein:.0f}g de {goal:.0f}g "
                    f"({pct * 100:.0f}% da meta).",
            action="Continue priorizando proteínas.",
            metric_value=protein,
            metric_label="Proteína consumida",
        )

    return None


def glp1_low_calorie_alert(daily_summary_fn) -> NutritionAlert | None:
    """
    Alerta GLP-1: <900 kcal por 3+ dias consecutivos.
    
    Args:
        daily_summary_fn: Função que retorna resumo diário
    
    Returns:
        NutritionAlert ou None
    """
    try:
        consecutive = 0
        for i in range(_GLP1_LOW_KCAL_DAYS):
            d = (date.today() - timedelta(days=i)).isoformat()
            summary = daily_summary_fn(d)
            calories = summary.get("calories", 0)
            
            if 0 < calories < _GLP1_LOW_KCAL_THRESHOLD:
                consecutive += 1
            else:
                break

        if consecutive >= _GLP1_LOW_KCAL_DAYS:
            return NutritionAlert(
                category=AlertCategory.GLP1,
                severity=AlertSeverity.WARNING,
                title="💉 Consumo calórico baixo com GLP-1",
                message=f"Consumo abaixo de {_GLP1_LOW_KCAL_THRESHOLD} kcal "
                        f"por {consecutive} dias consecutivos.",
                action="Com GLP-1 é essencial manter ingestão adequada. "
                       "Consulte seu médico.",
                metric_value=consecutive,
                metric_label="Dias consecutivos",
            )
    except Exception as e:
        logger.warning(f"glp1_low_calorie_alert: {e}")

    return None


def bariatric_volume_alert(volume_ml: float, phase: str) -> NutritionAlert | None:
    """
    Alerta de volume para fase bariátrica.
    
    Args:
        volume_ml: Volume consumido (ml)
        phase: Fase bariátrica (liquid/pasty/soft/solid/maintenance)
    
    Returns:
        NutritionAlert ou None
    """
    if not phase or volume_ml <= 0:
        return None

    phase_data = config.BARIATRIC_PHASES.get(phase, {})
    if not phase_data:
        return None

    max_ml = phase_data.get("max_ml", 999)

    # Excedeu o limite
    if volume_ml > max_ml:
        return NutritionAlert(
            category=AlertCategory.VOLUME,
            severity=AlertSeverity.WARNING,
            title="🔪 Volume excedido",
            message=f"Volume: {volume_ml:.0f}ml excede o limite "
                    f"da fase {phase_data.get('name', '')} ({max_ml}ml).",
            action="Fracione as refeições em porções menores.",
            metric_value=volume_ml,
            metric_label="Volume (ml)",
        )

    # Próximo do limite
    if volume_ml > max_ml * _BARIATRIC_VOLUME_PCT:
        return NutritionAlert(
            category=AlertCategory.VOLUME,
            severity=AlertSeverity.INFO,
            title="⚠️ Volume próximo do limite",
            message=f"Volume: {volume_ml:.0f}ml (limite {max_ml}ml).",
            action="Atenção ao volume das próximas refeições.",
            metric_value=volume_ml,
            metric_label="Volume (ml)",
        )

    return None


def protein_two_day_alert(
    daily_summary_fn,
    prot_goal: float,
) -> NutritionAlert | None:
    """
    Alerta de proteína <50% da meta por 2 dias consecutivos.
    
    Args:
        daily_summary_fn: Função que retorna resumo diário
        prot_goal: Meta de proteína diária
    
    Returns:
        NutritionAlert ou None
    """
    if prot_goal <= 0:
        return None

    try:
        low_days = 0
        for i in range(2):
            d = (date.today() - timedelta(days=i)).isoformat()
            summary = daily_summary_fn(d)
            protein = summary.get("protein", 0)
            
            if protein < prot_goal * _PROTEIN_WARNING_PCT:
                low_days += 1

        if low_days >= 2:
            return NutritionAlert(
                category=AlertCategory.PROTEIN,
                severity=AlertSeverity.WARNING,
                title="🥩 Proteína baixa por 2 dias",
                message=f"Proteína abaixo de 50% da meta por {low_days} dias consecutivos.",
                action="Priorize fontes proteicas nas próximas refeições.",
                metric_value=low_days,
                metric_label="Dias consecutivos",
            )
    except Exception as e:
        logger.warning(f"protein_two_day_alert: {e}")

    return None


def meal_timing_alert(meals: list) -> NutritionAlert | None:
    """
    Alerta de horário das refeições.
    
    Args:
        meals: Lista de refeições do dia
    
    Returns:
        NutritionAlert ou None
    """
    if not meals:
        return NutritionAlert(
            category=AlertCategory.TIMING,
            severity=AlertSeverity.WARNING,
            title="⏰ Nenhuma refeição registrada hoje",
            message="Você ainda não registrou refeições hoje.",
            action="Registre sua primeira refeição do dia.",
        )

    # Verifica se tem refeições em horários adequados
    has_breakfast = any(
        meal.meal_type == "cafe_manha" for meal in meals
    )
    has_lunch = any(
        meal.meal_type == "almoco" for meal in meals
    )
    has_dinner = any(
        meal.meal_type == "jantar" for meal in meals
    )

    if not has_breakfast:
        return NutritionAlert(
            category=AlertCategory.TIMING,
            severity=AlertSeverity.INFO,
            title="☀️ Café da manhã não registrado",
            message="Uma refeição matinal ajuda a regular o metabolismo.",
            action="Que tal um café da manhã nutritivo?",
        )

    if not has_lunch:
        return NutritionAlert(
            category=AlertCategory.TIMING,
            severity=AlertSeverity.INFO,
            title="🍽️ Almoço não registrado",
            message="O almoço é uma refeição importante para manter energia.",
            action="Registre seu almoço para manter consistência.",
        )

    if not has_dinner:
        return NutritionAlert(
            category=AlertCategory.TIMING,
            severity=AlertSeverity.INFO,
            title="🌙 Jantar não registrado",
            message="Uma refeição leve no fim do dia ajuda na recuperação.",
            action="Considere registrar seu jantar.",
        )

    return None


def hydration_alert(hydration: float, goal: float) -> NutritionAlert | None:
    """
    Alerta de hidratação insuficiente.
    
    Args:
        hydration: Água consumida (ml)
        goal: Meta de água (ml)
    
    Returns:
        NutritionAlert ou None
    """
    if goal <= 0 or hydration <= 0:
        return None

    pct = hydration / goal

    # Crítico: muito abaixo
    if pct < _HYDRATION_CRITICAL_PCT:
        return NutritionAlert(
            category=AlertCategory.HYDRATION,
            severity=AlertSeverity.CRITICAL,
            title="🚨 Hidratação crítica",
            message=f"Você consumiu apenas {hydration:.0f}ml de água "
                    f"({pct * 100:.0f}% da meta).",
            action="Pare agora e beba um copo de água. Seu corpo agradece!",
            metric_value=hydration,
            metric_label="Água consumida (ml)",
        )

    # Atenção: abaixo de 60%
    if pct < _HYDRATION_WARNING_PCT:
        remaining = goal - hydration
        return NutritionAlert(
            category=AlertCategory.HYDRATION,
            severity=AlertSeverity.WARNING,
            title="💧 Hidratação baixa",
            message=f"Você consumiu {hydration:.0f}ml de {goal:.0f}ml "
                    f"({pct * 100:.0f}% da meta).",
            action=f"Beba mais {remaining:.0f}ml de água.",
            metric_value=hydration,
            metric_label="Água consumida (ml)",
        )

    # Boa
    if pct >= _HYDRATION_GOOD_PCT:
        return NutritionAlert(
            category=AlertCategory.HYDRATION,
            severity=AlertSeverity.INFO,
            title="💧 Hidratação em dia!",
            message=f"Você consumiu {hydration:.0f}ml de água "
                    f"({pct * 100:.0f}% da meta).",
            action="Continue assim!",
            metric_value=hydration,
            metric_label="Água consumida (ml)",
        )

    return None


def fiber_alert(fiber: float, goal: float = _FIBER_MIN_GOAL) -> NutritionAlert | None:
    """
    Alerta de fibras insuficientes.
    
    Args:
        fiber: Fibras consumidas (g)
        goal: Meta de fibras (g)
    
    Returns:
        NutritionAlert ou None
    """
    if goal <= 0 or fiber <= 0:
        return None

    pct = fiber / goal

    if pct < _FIBER_WARNING_PCT:
        return NutritionAlert(
            category=AlertCategory.FIBER,
            severity=AlertSeverity.WARNING,
            title="🌾 Fibras abaixo do recomendado",
            message=f"Você consumiu {fiber:.1f}g de fibras "
                    f"({pct * 100:.0f}% da recomendação).",
            action="Inclua frutas, vegetais ou cereais integrais.",
            metric_value=fiber,
            metric_label="Fibras (g)",
        )

    if pct >= _FIBER_GOOD_PCT:
        return NutritionAlert(
            category=AlertCategory.FIBER,
            severity=AlertSeverity.INFO,
            title="🌾 Boa ingestão de fibras!",
            message=f"Você consumiu {fiber:.1f}g de fibras.",
            action="Continue com alimentos ricos em fibras.",
            metric_value=fiber,
            metric_label="Fibras (g)",
        )

    return None


def meal_balance_alert(meal: dict) -> NutritionAlert | None:
    """
    Alerta de balanceamento de uma refeição.
    
    Args:
        meal: Dicionário com dados da refeição
    
    Returns:
        NutritionAlert ou None
    """
    # Extrai dados (suporta PT e EN)
    protein = meal.get("protein", meal.get("proteina", 0))
    carbs = meal.get("carbs", meal.get("carboidratos", 0))
    fat = meal.get("fat", meal.get("gorduras", 0))
    calories = meal.get("calories", meal.get("calorias", 0))

    if calories <= 0:
        return None

    # Calcula proporção de calorias
    protein_cal = protein * 4
    carbs_cal = carbs * 4
    fat_cal = fat * 9
    total_cal = protein_cal + carbs_cal + fat_cal

    if total_cal == 0:
        return None

    protein_pct = (protein_cal / total_cal) * 100
    carbs_pct = (carbs_cal / total_cal) * 100
    fat_pct = (fat_cal / total_cal) * 100

    # Muito alta em gordura
    if fat_pct > 50:
        return NutritionAlert(
            category=AlertCategory.BALANCE,
            severity=AlertSeverity.INFO,
            title="⚖️ Refeição rica em gordura",
            message=f"Esta refeição tem {fat_pct:.0f}% de gordura.",
            action="Considere reduzir gorduras e balancear com proteínas.",
            metric_value=fat_pct,
            metric_label="% Gordura",
        )

    # Muito alta em carboidratos
    if carbs_pct > 70 and protein_pct < 15:
        return NutritionAlert(
            category=AlertCategory.BALANCE,
            severity=AlertSeverity.INFO,
            title="⚖️ Refeição rica em carboidratos",
            message=f"Esta refeição tem {carbs_pct:.0f}% de carboidratos "
                    f"e apenas {protein_pct:.0f}% de proteína.",
            action="Adicione uma fonte proteica para melhorar o balanço.",
            metric_value=carbs_pct,
            metric_label="% Carboidratos",
        )

    return None


# ─────────────────────────────────────────────────────────────────────────────
# NUTRIENT SCORING
# ─────────────────────────────────────────────────────────────────────────────

def nutrient_score(food: dict) -> int:
    """
    Calcula score nutricional 0-100 para um alimento.
    
    Args:
        food: Dicionário com dados do alimento
    
    Returns:
        Score (0-100)
    """
    # Extrai dados (suporta PT e EN)
    protein = food.get("protein", food.get("proteina", 0))
    fiber = food.get("fiber", food.get("fibra", 0))
    calories = food.get("calories", food.get("calorias", 0))
    fat = food.get("fat", food.get("gorduras", 0))
    carbs = food.get("carbs", food.get("carboidratos", 0))

    score = 50  # Base

    # Proteína: +20 se >20g, +10 se >10g
    if protein > 20:
        score += 20
    elif protein > 10:
        score += 10

    # Fibras: +15 se >5g, +7 se >2g
    if fiber > 5:
        score += 15
    elif fiber > 2:
        score += 7

    # Calorias: penaliza se >300 e baixa proteína
    if calories > 300 and protein < 5 and fiber < 1:
        score -= 20

    # Gorduras: penaliza se >30% das calorias
    if calories > 0 and fat > 0:
        fat_cal = fat * 9
        fat_pct = (fat_cal / calories) * 100
        if fat_pct > 30:
            score -= 10

    # Carboidratos: penaliza se >60% e baixa fibra
    if calories > 0 and carbs > 0:
        carbs_cal = carbs * 4
        carbs_pct = (carbs_cal / calories) * 100
        if carbs_pct > 60 and fiber < 2:
            score -= 10

    return max(0, min(100, score))


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _create_alert(
    category: AlertCategory,
    severity: AlertSeverity,
    message: str,
    action: str = "",
    metric_value: float | None = None,
    metric_label: str = "",
) -> NutritionAlert:
    """
    Cria um alerta nutricional.
    
    Args:
        category: Categoria do alerta
        severity: Severidade
        message: Mensagem
        action: Ação sugerida
        metric_value: Valor da métrica
        metric_label: Label da métrica
    
    Returns:
        Objeto NutritionAlert
    """
    # Gera título baseado na categoria e severidade
    titles = {
        AlertCategory.CALORIE: {
            AlertSeverity.INFO: "Meta calórica",
            AlertSeverity.WARNING: "Calorias abaixo",
            AlertSeverity.CRITICAL: "Calorias críticas",
        },
        AlertCategory.PROTEIN: {
            AlertSeverity.INFO: "Proteína excelente",
            AlertSeverity.WARNING: "Proteína baixa",
            AlertSeverity.CRITICAL: "Proteína crítica",
        },
        AlertCategory.HYDRATION: {
            AlertSeverity.INFO: "Hidratação em dia",
            AlertSeverity.WARNING: "Hidratação baixa",
            AlertSeverity.CRITICAL: "Hidratação crítica",
        },
        AlertCategory.FIBER: {
            AlertSeverity.INFO: "Fibras boas",
            AlertSeverity.WARNING: "Fibras baixas",
            AlertSeverity.CRITICAL: "Fibras críticas",
        },
    }

    default_title = f"{category.value.capitalize()} {severity.value}"
    title = titles.get(category, {}).get(severity, default_title)

    return NutritionAlert(
        category=category,
        severity=severity,
        title=title,
        message=message,
        action=action,
        metric_value=metric_value,
        metric_label=metric_label,
    )


def get_alerts_for_user(
    user: dict,
    daily_summary_fn=None,
    meals: list | None = None,
    hydration: float | None = None,
) -> list[NutritionAlert]:
    """
    Obtém todos os alertas nutricionais para um usuário.
    
    Args:
        user: Dicionário com dados do usuário
        daily_summary_fn: Função de resumo diário (opcional)
        meals: Lista de refeições (opcional)
        hydration: Total de água (opcional)
    
    Returns:
        Lista de alertas
    """
    alerts = []

    # Configurações do usuário
    weight = user.get("current_weight")
    height = user.get("height")
    age = user.get("age")
    gender = user.get("gender", "female")
    health_mode = user.get("health_mode", "general")
    goal = user.get("goal", "lose")
    activity_level = user.get("activity_level", "moderate")

    # Se não houver daily_summary_fn, não podemos gerar alertas de calorias/proteína
    if daily_summary_fn:
        try:
            summary = daily_summary_fn()
            
            # Calcula metas
            from services.nutrition_service import NutritionService
            # Usa cálculo direto para evitar dependência circular
            # TMB aproximada
            tmb = 1500
            if weight and height and age:
                if gender == "male":
                    tmb = int(10 * weight + 6.25 * height - 5 * age + 5)
                else:
                    tmb = int(10 * weight + 6.25 * height - 5 * age - 161)
            
            tdee = int(tmb * config.ACTIVITY_FACTORS.get(activity_level, 1.55))
            
            if health_mode == "bariatric":
                goal_cal = max(config.MIN_CALORIES_SAFE, tdee - 300)
            elif health_mode == "glp1":
                goal_cal = max(config.MIN_CALORIES_SAFE, tdee - 400)
            elif goal == "lose":
                goal_cal = max(config.SAFE_MIN_CALORIES, tdee - 500)
            elif goal == "gain":
                goal_cal = tdee + 300
            else:
                goal_cal = tdee
            
            # Meta de proteína
            if weight:
                prot_goal_map = {
                    "glp1": config.GLP1_PROTEIN_PER_KG,
                    "bariatric": config.BARIATRIC_PROTEIN_PER_KG,
                    "fitness": config.FITNESS_PROTEIN_PER_KG,
                    "general": config.GENERAL_PROTEIN_PER_KG,
                }
                prot_goal = weight * prot_goal_map.get(health_mode, config.GENERAL_PROTEIN_PER_KG)
            else:
                prot_goal = 120.0

            # Meta de água
            water_goal = config.HYDRATION_GOAL_ML

            # Gera alertas
            cal_alert = calorie_alert(summary.get("calories", 0), goal_cal)
            if cal_alert:
                alerts.append(cal_alert)

            prot_alert = protein_alert(summary.get("protein", 0), prot_goal)
            if prot_alert:
                alerts.append(prot_alert)

            # GLP-1
            if health_mode == "glp1":
                glp1_alert = glp1_low_calorie_alert(daily_summary_fn)
                if glp1_alert:
                    alerts.append(glp1_alert)
                
                # Alerta de proteína 2 dias
                two_day_alert = protein_two_day_alert(daily_summary_fn, prot_goal)
                if two_day_alert:
                    alerts.append(two_day_alert)

            # Bariátrica
            if health_mode == "bariatric":
                volume = summary.get("volume_ml", 0)
                phase = user.get("bariatric_phase", "liquid")
                volume_alert = bariatric_volume_alert(volume, phase)
                if volume_alert:
                    alerts.append(volume_alert)

            # Hidratação
            if hydration is None:
                hydration = summary.get("volume_ml", 0)
            
            hyd_alert = hydration_alert(hydration, water_goal)
            if hyd_alert:
                alerts.append(hyd_alert)

            # Fibras
            fiber = summary.get("fiber", 0)
            fiber_alert_obj = fiber_alert(fiber)
            if fiber_alert_obj:
                alerts.append(fiber_alert_obj)

        except Exception as e:
            logger.warning(f"get_alerts_for_user: {e}")

    # Alertas de horário das refeições
    if meals is None:
        try:
            from services.nutrition_service import NutritionService
            # Tenta buscar refeições
            pass  # Será feito pela função caller
        except Exception:
            pass
    
    if meals:
        timing_alert = meal_timing_alert(meals)
        if timing_alert:
            alerts.append(timing_alert)

    return alerts


def get_critical_alerts_for_user(user: dict, **kwargs) -> list[NutritionAlert]:
    """
    Retorna apenas alertas críticos para um usuário.
    
    Args:
        user: Dicionário com dados do usuário
        **kwargs: Argumentos passados para get_alerts_for_user
    
    Returns:
        Lista de alertas críticos
    """
    alerts = get_alerts_for_user(user, **kwargs)
    return [a for a in alerts if a.is_critical]


__all__ = [
    # Alert generators
    "calorie_alert",
    "protein_alert",
    "glp1_low_calorie_alert",
    "bariatric_volume_alert",
    "protein_two_day_alert",
    "meal_timing_alert",
    "hydration_alert",
    "fiber_alert",
    "meal_balance_alert",
    # Nutrient scoring
    "nutrient_score",
    # Alert aggregation
    "get_alerts_for_user",
    "get_critical_alerts_for_user",
    # Models
