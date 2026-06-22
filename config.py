"""
Melshape — Configurações Globais.

Centraliza todas as constantes, flags de ambiente e configurações do sistema.
Todas as importações externas ficam aqui.

Princípios:
- Toda constante que pode variar entre ambientes está aqui
- Agrupamento por domínio para fácil localização
- Validação de variáveis de ambiente críticas
- Fallbacks seguros para desenvolvimento
- Imutabilidade: configurações não mudam em runtime
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# ─────────────────────────────────────────────────────────────────────────────
# 1. IDENTIDADE DO PRODUTO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProductIdentity:
    """Metadados da aplicação."""
    name: Final[str] = "Melshape"
    tagline: Final[str] = "Para quem está mudando de verdade"
    icon: Final[str] = "🔥"
    version: Final[str] = "3.0.0"
    description: Final[str] = "Plataforma de transformação comportamental"


PRODUCT: Final = ProductIdentity()

# Aliases para compatibilidade com código existente
APP_NAME: Final[str] = PRODUCT.name
APP_TAGLINE: Final[str] = PRODUCT.tagline
APP_ICON: Final[str] = PRODUCT.icon
APP_VERSION: Final[str] = PRODUCT.version
APP_DESCRIPTION: Final[str] = PRODUCT.description

# ─────────────────────────────────────────────────────────────────────────────
# 2. AMBIENTE E DEPLOY
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EnvironmentConfig:
    """Configurações de ambiente e deploy."""
    env: Final[str] = os.getenv("MELSHAPE_ENV", "development")
    app_url: Final[str] = os.getenv("APP_URL", "http://localhost:8501")
    support_email: Final[str] = os.getenv("SUPPORT_EMAIL", "suporte@melshape.com.br")


ENV_CONFIG: Final = EnvironmentConfig()

# Aliases
ENV: Final[str] = ENV_CONFIG.env
APP_URL: Final[str] = ENV_CONFIG.app_url
SUPPORT_EMAIL: Final[str] = ENV_CONFIG.support_email

# ─────────────────────────────────────────────────────────────────────────────
# 3. DEMO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DemoConfig:
    """Credenciais e configurações do ambiente de demonstração."""
    email: Final[str] = os.getenv("DEMO_EMAIL", "demo@melshape.com.br")
    password: Final[str] = os.getenv("DEMO_PASSWORD", "demo123")


DEMO: Final = DemoConfig()

DEMO_EMAIL: Final[str] = DEMO.email
DEMO_PASSWORD: Final[str] = DEMO.password

# ─────────────────────────────────────────────────────────────────────────────
# 4. PLANOS E PREÇOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PricingConfig:
    """Configurações de planos e preços."""
    trial_days: Final[int] = int(os.getenv("TRIAL_DAYS", "10"))
    pro_price: Final[float] = float(os.getenv("PRO_PRICE", "19.90"))
    clinic_price: Final[float] = float(os.getenv("CLINIC_PRICE", "99.00"))
    lifetime_price: Final[float] = float(os.getenv("LIFETIME_PRICE", "399.00"))


PRICING: Final = PricingConfig()

TRIAL_DAYS: Final[int] = PRICING.trial_days
PRO_PRICE: Final[float] = PRICING.pro_price
CLINIC_PRICE: Final[float] = PRICING.clinic_price
LIFETIME_PRICE: Final[float] = PRICING.lifetime_price

# Nomes dos planos
PLAN_FREE: Final[str] = "free"
PLAN_TRIAL: Final[str] = "trial"
PLAN_PRO: Final[str] = "pro"
PLAN_CLINIC: Final[str] = "clinic"
PLAN_LIFETIME: Final[str] = "lifetime"

# ─────────────────────────────────────────────────────────────────────────────
# 5. NUTRIÇÃO E METAS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NutritionConfig:
    """Configurações de nutrição, metas e limites de segurança."""
    hydration_goal_ml: Final[int] = 2500
    min_calories_safe: Final[int] = 800
    safe_min_calories: Final[int] = 1200
    max_calories_display: Final[int] = 5000
    alert_pct_warning: Final[float] = 0.85
    
    # Fatores de atividade física
    activity_factors: Final[dict[str, float]] = (
        ("sedentary", 1.2),
        ("light", 1.375),
        ("moderate", 1.55),
        ("active", 1.725),
        ("very_active", 1.9),
    )
    
    # Proteína por kg (por modo)
    general_protein_per_kg: Final[float] = 1.6
    fitness_protein_per_kg: Final[float] = 2.0
    glp1_protein_per_kg: Final[float] = 1.2
    bariatric_protein_per_kg: Final[float] = 1.5


NUTRITION: Final = NutritionConfig()

# Aliases
HYDRATION_GOAL_ML: Final[int] = NUTRITION.hydration_goal_ml
MIN_CALORIES_SAFE: Final[int] = NUTRITION.min_calories_safe
SAFE_MIN_CALORIES: Final[int] = NUTRITION.safe_min_calories
MAX_CALORIES_DISPLAY: Final[int] = NUTRITION.max_calories_display
ALERT_PCT_WARNING: Final[float] = NUTRITION.alert_pct_warning
ACTIVITY_FACTORS: Final[dict[str, float]] = dict(NUTRITION.activity_factors)
GENERAL_PROTEIN_PER_KG: Final[float] = NUTRITION.general_protein_per_kg
FITNESS_PROTEIN_PER_KG: Final[float] = NUTRITION.fitness_protein_per_kg
GLP1_PROTEIN_PER_KG: Final[float] = NUTRITION.glp1_protein_per_kg
BARIATRIC_PROTEIN_PER_KG: Final[float] = NUTRITION.bariatric_protein_per_kg

# ─────────────────────────────────────────────────────────────────────────────
# 6. GLP-1
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GLP1Config:
    """Configurações específicas para usuários de GLP-1."""
    medications: Final[tuple[str, ...]] = (
        "Ozempic (Semaglutida)",
        "Wegovy (Semaglutida)",
        "Mounjaro (Tirzepatida)",
        "Zepbound (Tirzepatida)",
        "Victoza (Liraglutida)",
        "Saxenda (Liraglutida)",
        "Outro",
    )
    
    doses: Final[dict[str, tuple[str, ...]]] = (
        ("Ozempic (Semaglutida)", ("0.25mg", "0.5mg", "1mg", "2mg")),
        ("Wegovy (Semaglutida)", ("0.25mg", "0.5mg", "1mg", "1.7mg", "2.4mg")),
        ("Mounjaro (Tirzepatida)", ("2.5mg", "5mg", "7.5mg", "10mg", "12.5mg", "15mg")),
        ("Zepbound (Tirzepatida)", ("2.5mg", "5mg", "7.5mg", "10mg", "12.5mg", "15mg")),
        ("Victoza (Liraglutida)", ("0.6mg", "1.2mg", "1.8mg")),
        ("Saxenda (Liraglutida)", ("0.6mg", "1.2mg", "1.8mg", "2.4mg", "3mg")),
        ("Outro", ("Personalizado",)),
    )
    
    phases: Final[dict[str, str]] = (
        ("adapting", "🔬 Adaptação"),
        ("maintenance", "✅ Manutenção"),
        ("tapering", "📉 Desmame"),
        ("stopped", "⏹️ Parado"),
    )
    
    low_kcal_threshold: Final[int] = 900
    low_kcal_days: Final[int] = 3


GLP1: Final = GLP1Config()

# Aliases
GLP1_MEDICATIONS: Final[list[str]] = list(GLP1.medications)
GLP1_DOSES: Final[dict[str, list[str]]] = {k: list(v) for k, v in GLP1.doses}
GLP1_PHASES: Final[dict[str, str]] = dict(GLP1.phases)
GLP1_LOW_KCAL_THRESHOLD: Final[int] = GLP1.low_kcal_threshold
GLP1_LOW_KCAL_DAYS: Final[int] = GLP1.low_kcal_days

# ─────────────────────────────────────────────────────────────────────────────
# 7. BARIÁTRICA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BariatricPhase:
    """Fase pós-operatória da cirurgia bariátrica."""
    name: str
    days: str
    max_ml: int
    max_cal: int


@dataclass(frozen=True)
class BariatricSupplement:
    """Suplemento essencial pós-bariátrica."""
    name: str
    dose: str
    unit: str


@dataclass(frozen=True)
class BariatricConfig:
    """Configurações para usuários bariátricos."""
    types: Final[dict[str, str]] = (
        ("sleeve", "Sleeve (Gastrectomia Vertical)"),
        ("bypass", "Bypass Gástrico (Y de Roux)"),
        ("band", "Banda Gástrica"),
        ("balloon", "Balão Gástrico"),
        ("other", "Outro"),
    )
    
    phases: Final[dict[str, BariatricPhase]] = (
        ("liquid", BariatricPhase("Líquida", "0–14", 200, 600)),
        ("pasty", BariatricPhase("Pastosa", "15–30", 250, 700)),
        ("soft", BariatricPhase("Branda", "31–60", 350, 900)),
        ("solid", BariatricPhase("Sólida", "61–180", 500, 1200)),
        ("maintenance", BariatricPhase("Manutenção", "181+", 700, 1500)),
    )
    
    essentials: Final[tuple[BariatricSupplement, ...]] = (
        BariatricSupplement("Vitamina B12", "1000", "mcg"),
        BariatricSupplement("Vitamina D3", "2000", "UI"),
        BariatricSupplement("Ferro", "45", "mg"),
        BariatricSupplement("Cálcio Citrato", "1200", "mg"),
        BariatricSupplement("Zinco", "15", "mg"),
        BariatricSupplement("Vitamina B1 (Tiamina)", "100", "mg"),
        BariatricSupplement("Proteína Whey", "30", "g"),
    )


BARIATRIC: Final = BariatricConfig()

# Aliases
BARIATRIC_TYPES: Final[dict[str, str]] = dict(BARIATRIC.types)
BARIATRIC_PHASES: Final[dict[str, dict[str, str | int]]] = {
    k: {"name": v.name, "days": v.days, "max_ml": v.max_ml, "max_cal": v.max_cal}
    for k, v in BARIATRIC.phases
}
BARIATRIC_ESSENTIALS: Final[list[dict[str, str]]] = [
    {"name": s.name, "dose": s.dose, "unit": s.unit}
    for s in BARIATRIC.essentials
]

# ─────────────────────────────────────────────────────────────────────────────
# 8. GAMIFICAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GamificationConfig:
    """Sistema de XP e recompensas."""
    # XP por ação
    xp_checkin: Final[int] = 50
    xp_refeicao: Final[int] = 25
    xp_peso: Final[int] = 30
    xp_habito: Final[int] = 20
    xp_suplemento: Final[int] = 10
    xp_treino: Final[int] = 40
    xp_glp1: Final[int] = 25
    xp_medida: Final[int] = 15
    xp_foto: Final[int] = 10
    
    # Bônus por streaks
    xp_streak_7: Final[int] = 100
    xp_streak_14: Final[int] = 200
    xp_streak_30: Final[int] = 500
    xp_streak_90: Final[int] = 1000
    
    # Meta concluída
    xp_meta_concluida: Final[int] = 200


GAMIFICATION: Final = GamificationConfig()

# Aliases
XP_CHECKIN: Final[int] = GAMIFICATION.xp_checkin
XP_REFEICAO: Final[int] = GAMIFICATION.xp_refeicao
XP_PESO: Final[int] = GAMIFICATION.xp_peso
XP_HABITO: Final[int] = GAMIFICATION.xp_habito
XP_SUPLEMENTO: Final[int] = GAMIFICATION.xp_suplemento
XP_TREINO: Final[int] = GAMIFICATION.xp_treino
XP_GLP1: Final[int] = GAMIFICATION.xp_glp1
XP_MEDIDA: Final[int] = GAMIFICATION.xp_medida
XP_FOTO: Final[int] = GAMIFICATION.xp_foto
XP_STREAK_7: Final[int] = GAMIFICATION.xp_streak_7
XP_STREAK_14: Final[int] = GAMIFICATION.xp_streak_14
XP_STREAK_30: Final[int] = GAMIFICATION.xp_streak_30
XP_STREAK_90: Final[int] = GAMIFICATION.xp_streak_90
XP_META_CONCLUIDA: Final[int] = GAMIFICATION.xp_meta_concluida

# ─────────────────────────────────────────────────────────────────────────────
# 9. SINTOMAS GLP-1
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SymptomsConfig:
    """Lista de sintomas e severidade."""
    symptom_list: Final[tuple[tuple[str, str], ...]] = (
        ("nausea", "Náusea"),
        ("vomiting", "Vômito"),
        ("dizziness", "Tontura"),
        ("pain", "Dor abdominal"),
        ("constipation", "Constipação"),
        ("diarrhea", "Diarreia"),
        ("fatigue", "Fadiga"),
        ("headache", "Dor de cabeça"),
        ("heartburn", "Azia/Refluxo"),
        ("low_appetite", "Falta de apetite"),
    )
    
    severe_symptoms: Final[frozenset[str]] = frozenset({
        "nausea", "vomiting", "pain", "dizziness"
    })


SYMPTOMS: Final = SymptomsConfig()

SYMPTOM_LIST: Final[list[tuple[str, str]]] = list(SYMPTOMS.symptom_list)
SEVERE_SYMPTOMS: Final[set[str]] = set(SYMPTOMS.severe_symptoms)

# ─────────────────────────────────────────────────────────────────────────────
# 10. TREINO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WorkoutConfig:
    """Tipos de treino suportados."""
    types: Final[dict[str, str]] = (
        ("strength", "🏋️ Musculação"),
        ("cardio", "🏃 Cardio"),
        ("hiit", "⚡ HIIT"),
        ("yoga", "🧘 Yoga/Pilates"),
        ("swimming", "🏊 Natação"),
        ("cycling", "🚴 Ciclismo"),
        ("walking", "🚶 Caminhada"),
        ("functional", "💪 Funcional"),
        ("sports", "⚽ Esporte"),
        ("other", "🎯 Outro"),
    )


WORKOUT: Final = WorkoutConfig()
WORKOUT_TYPES: Final[dict[str, str]] = dict(WORKOUT.types)

# ─────────────────────────────────────────────────────────────────────────────
# 11. HIDRATAÇÃO RÁPIDA
# ─────────────────────────────────────────────────────────────────────────────

QUICK_ADD_ML: Final[tuple[int, ...]] = (200, 300, 500, 750)

# ─────────────────────────────────────────────────────────────────────────────
# 12. MENSAGENS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MessagesConfig:
    """Mensagens motivacionais e disclaimers."""
    motivational: Final[dict[str, tuple[str, ...]]] = (
        ("general", (
            "Consistência bate perfeição todos os dias.",
            "Um dia de cada vez. Isso é tudo que precisa.",
            "Você não precisa ser extremo. Só precisa ser constante.",
            "Cada escolha alimentar é um voto pela pessoa que você quer ser.",
            "O resultado é consequência. O hábito é a causa.",
        )),
        ("fitness", (
            "O corpo muda devagar. A disciplina muda rápido.",
            "Cada treino é uma promessa cumprida com você mesmo.",
            "Força não é só física.",
            "Proteína primeiro. Sempre.",
            "Descanso é parte do treino, não ausência dele.",
        )),
        ("bariatric", (
            "Cada refeição certa é uma vitória clínica real.",
            "Seu corpo está se reconstruindo. Respeite o processo.",
            "Pequenas porções, grandes resultados.",
            "A cirurgia foi o começo. O hábito é o trabalho real.",
            "Mastigue devagar. Seu novo estômago agradece.",
        )),
        ("glp1", (
            "O medicamento abre a porta. Você decide o que entra.",
            "Proteína primeiro. Sempre.",
            "Adesão ao tratamento é parte da transformação.",
            "Cada dose registrada é um compromisso com sua saúde.",
            "O remédio controla a fome. Você controla as escolhas.",
        )),
    )
    
    medical_disclaimer: Final[str] = (
        "⚕️ O Melshape é uma ferramenta de apoio e não substitui orientação "
        "médica ou nutricional profissional. Em caso de sintomas graves ou "
        "dúvidas sobre seu tratamento, procure seu médico."
    )


MESSAGES: Final = MessagesConfig()

MENSAGENS_MOTIVACIONAIS: Final[dict[str, list[str]]] = {
    k: list(v) for k, v in MESSAGES.motivational
}
MEDICAL_DISCLAIMER: Final[str] = MESSAGES.medical_disclaimer

# ─────────────────────────────────────────────────────────────────────────────
# 13. LOGGING
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LoggingConfig:
    """Configurações de logging."""
    level: Final[int] = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper())
    format: Final[str] = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format: Final[str] = "%Y-%m-%d %H:%M:%S"


LOGGING_CONFIG: Final = LoggingConfig()

LOG_LEVEL: Final[int] = LOGGING_CONFIG.level
LOG_FORMAT: Final[str] = LOGGING_CONFIG.format
LOG_DATE_FORMAT: Final[str] = LOGGING_CONFIG.date_format

# ─────────────────────────────────────────────────────────────────────────────
# 14. VALIDAÇÃO DE AMBIENTE
# ─────────────────────────────────────────────────────────────────────────────

def validate_environment() -> list[str]:
    """
    Valida variáveis de ambiente críticas.
    
    Returns:
        Lista de warnings (vazia se tudo ok).
    """
    warnings: list[str] = []
    
    # Supabase é crítico em produção
    if ENV in ("staging", "production"):
        if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
            warnings.append("⚠️ SUPABASE_URL e SUPABASE_KEY são obrigatórios em produção")
    
    # Resend é recomendado em produção
    if ENV in ("staging", "production"):
        if not os.getenv("RESEND_API_KEY"):
            warnings.append("⚠️ RESEND_API_KEY não configurado — emails não serão enviados")
    
    return warnings


# Executa validação ao importar
ENV_WARNINGS: Final[list[str]] = validate_environment()

if ENV_WARNINGS:
    for warning in ENV_WARNINGS:
        print(warning)

# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS PÚBLICOS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Identidade
    "APP_NAME", "APP_TAGLINE", "APP_ICON", "APP_VERSION", "APP_DESCRIPTION",
    # Ambiente
    "ENV", "APP_URL", "SUPPORT_EMAIL",
    # Demo
    "DEMO_EMAIL", "DEMO_PASSWORD",
    # Planos
    "TRIAL_DAYS", "PRO_PRICE", "CLINIC_PRICE", "LIFETIME_PRICE",
    "PLAN_FREE", "PLAN_TRIAL", "PLAN_PRO", "PLAN_CLINIC", "PLAN_LIFETIME",
    # Nutrição
    "HYDRATION_GOAL_ML", "MIN_CALORIES_SAFE", "SAFE_MIN_CALORIES",
    "MAX_CALORIES_DISPLAY", "ALERT_PCT_WARNING", "ACTIVITY_FACTORS",
    "GENERAL_PROTEIN_PER_KG", "FITNESS_PROTEIN_PER_KG",
    "GLP1_PROTEIN_PER_KG", "BARIATRIC_PROTEIN_PER_KG",
    # GLP-1
    "GLP1_MEDICATIONS", "GLP1_DOSES", "GLP1_PHASES",
    "GLP1_LOW_KCAL_THRESHOLD", "GLP1_LOW_KCAL_DAYS",
    # Bariátrica
    "BARIATRIC_TYPES", "BARIATRIC_PHASES", "BARIATRIC_ESSENTIALS",
    # Gamificação
    "XP_CHECKIN", "XP_REFEICAO", "XP_PESO", "XP_HABITO", "XP_SUPLEMENTO",
    "XP_TREINO", "XP_GLP1", "XP_MEDIDA", "XP_FOTO",
    "XP_STREAK_7", "XP_STREAK_14", "XP_STREAK_30", "XP_STREAK_90",
    "XP_META_CONCLUIDA",
    # Sintomas
    "SYMPTOM_LIST", "SEVERE_SYMPTOMS",
    # Treino
    "WORKOUT_TYPES",
    # Hidratação
    "QUICK_ADD_ML",
    # Mensagens
    "MENSAGENS_MOTIVACIONAIS", "MEDICAL_DISCLAIMER",
    # Logging
    "LOG_LEVEL", "LOG_FORMAT", "LOG_DATE_FORMAT",
    # Validação
    "ENV_WARNINGS", "validate_environment",
]
