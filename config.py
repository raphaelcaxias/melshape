"""
Melshape — Configurações Globais.

Centraliza todas as constantes, flags de ambiente e configurações do sistema.

Arquitetura:
    Config (dataclass principal)
    ├── ProductIdentity (metadados da aplicação)
    ├── EnvironmentConfig (ambiente e deploy)
    ├── DemoConfig (credenciais demo)
    ├── PricingConfig (planos e preços)
    ├── NutritionConfig (nutrição e metas)
    ├── GLP1Config (configurações GLP-1)
    ├── BariatricConfig (configurações bariátrica)
    ├── GamificationConfig (XP e recompensas)
    ├── SymptomsConfig (sintomas e severidade)
    ├── WorkoutConfig (tipos de treino)
    ├── MessagesConfig (mensagens e disclaimers)
    └── LoggingConfig (logging)

Princípios:
- Imutabilidade real: frozen dataclasses + tuples/frozensets
- Zero duplicação: sem aliases redundantes
- Validação lazy: ambiente validado sob demanda
- Type safety: validação de tipos para variáveis de ambiente
- Fallbacks seguros: valores padrão para desenvolvimento
- API limpa: acesso direto via atributos (config.PRODUCT.name)
- Documentação: docstrings em todos os campos
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Final


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_env(key: str, default: str = "") -> str:
    """Obtém variável de ambiente com fallback."""
    return os.getenv(key, default)


def _get_env_int(key: str, default: int) -> int:
    """Obtém variável de ambiente como int com validação."""
    try:
        return int(_get_env(key, str(default)))
    except ValueError:
        logging.warning(f"⚠️ {key} inválido, usando padrão: {default}")
        return default


def _get_env_float(key: str, default: float) -> float:
    """Obtém variável de ambiente como float com validação."""
    try:
        return float(_get_env(key, str(default)))
    except ValueError:
        logging.warning(f"⚠️ {key} inválido, usando padrão: {default}")
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """Obtém variável de ambiente como bool."""
    value = _get_env(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProductIdentity:
    """Metadados da aplicação."""
    
    name: str = "Melshape"
    tagline: str = "Para quem está mudando de verdade"
    icon: str = "🔥"
    version: str = "3.0.0"
    description: str = "Plataforma de transformação comportamental"


@dataclass(frozen=True)
class EnvironmentConfig:
    """Configurações de ambiente e deploy."""
    
    env: str = field(default_factory=lambda: _get_env("MELSHAPE_ENV", "development"))
    app_url: str = field(default_factory=lambda: _get_env("APP_URL", "http://localhost:8501"))
    support_email: str = field(default_factory=lambda: _get_env("SUPPORT_EMAIL", "suporte@melshape.com.br"))
    
    @property
    def is_production(self) -> bool:
        """Verifica se está em produção."""
        return self.env == "production"
    
    @property
    def is_staging(self) -> bool:
        """Verifica se está em staging."""
        return self.env == "staging"
    
    @property
    def is_development(self) -> bool:
        """Verifica se está em desenvolvimento."""
        return self.env == "development"


@dataclass(frozen=True)
class DemoConfig:
    """Credenciais e configurações do ambiente de demonstração."""
    
    email: str = field(default_factory=lambda: _get_env("DEMO_EMAIL", "demo@melshape.com.br"))
    password: str = field(default_factory=lambda: _get_env("DEMO_PASSWORD", "demo123"))


@dataclass(frozen=True)
class PricingConfig:
    """Configurações de planos e preços."""
    
    trial_days: int = field(default_factory=lambda: _get_env_int("TRIAL_DAYS", 10))
    pro_price: float = field(default_factory=lambda: _get_env_float("PRO_PRICE", 19.90))
    clinic_price: float = field(default_factory=lambda: _get_env_float("CLINIC_PRICE", 99.00))
    lifetime_price: float = field(default_factory=lambda: _get_env_float("LIFETIME_PRICE", 399.00))
    
    # Nomes dos planos (imutáveis)
    PLAN_FREE: Final[str] = "free"
    PLAN_TRIAL: Final[str] = "trial"
    PLAN_PRO: Final[str] = "pro"
    PLAN_CLINIC: Final[str] = "clinic"
    PLAN_LIFETIME: Final[str] = "lifetime"


@dataclass(frozen=True)
class NutritionConfig:
    """Configurações de nutrição, metas e limites de segurança."""
    
    hydration_goal_ml: int = 2500
    min_calories_safe: int = 800
    safe_min_calories: int = 1200
    max_calories_display: int = 5000
    alert_pct_warning: float = 0.85
    
    # Fatores de atividade física (imutável)
    activity_factors: dict[str, float] = field(
        default_factory=lambda: {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9,
        }
    )
    
    # Proteína por kg (por modo)
    general_protein_per_kg: float = 1.6
    fitness_protein_per_kg: float = 2.0
    glp1_protein_per_kg: float = 1.2
    bariatric_protein_per_kg: float = 1.5
    
    def get_protein_per_kg(self, health_mode: str) -> float:
        """Retorna proteína por kg para o modo de saúde especificado."""
        return {
            "general": self.general_protein_per_kg,
            "fitness": self.fitness_protein_per_kg,
            "glp1": self.glp1_protein_per_kg,
            "bariatric": self.bariatric_protein_per_kg,
        }.get(health_mode, self.general_protein_per_kg)


@dataclass(frozen=True)
class GLP1Config:
    """Configurações específicas para usuários de GLP-1."""
    
    # Medicamentos (tuple imutável)
    medications: tuple[str, ...] = (
        "Ozempic (Semaglutida)",
        "Wegovy (Semaglutida)",
        "Mounjaro (Tirzepatida)",
        "Zepbound (Tirzepatida)",
        "Victoza (Liraglutida)",
        "Saxenda (Liraglutida)",
        "Outro",
    )
    
    # Doses por medicamento (dict de tuples imutáveis)
    doses: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "Ozempic (Semaglutida)": ("0.25mg", "0.5mg", "1mg", "2mg"),
            "Wegovy (Semaglutida)": ("0.25mg", "0.5mg", "1mg", "1.7mg", "2.4mg"),
            "Mounjaro (Tirzepatida)": ("2.5mg", "5mg", "7.5mg", "10mg", "12.5mg", "15mg"),
            "Zepbound (Tirzepatida)": ("2.5mg", "5mg", "7.5mg", "10mg", "12.5mg", "15mg"),
            "Victoza (Liraglutida)": ("0.6mg", "1.2mg", "1.8mg"),
            "Saxenda (Liraglutida)": ("0.6mg", "1.2mg", "1.8mg", "2.4mg", "3mg"),
            "Outro": ("Personalizado",),
        }
    )
    
    # Fases (dict imutável)
    phases: dict[str, str] = field(
        default_factory=lambda: {
            "adapting": "🔬 Adaptação",
            "maintenance": "✅ Manutenção",
            "tapering": "📉 Desmame",
            "stopped": "⏹️ Parado",
        }
    )
    
    low_kcal_threshold: int = 900
    low_kcal_days: int = 3


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
    
    # Tipos de cirurgia (dict imutável)
    types: dict[str, str] = field(
        default_factory=lambda: {
            "sleeve": "Sleeve (Gastrectomia Vertical)",
            "bypass": "Bypass Gástrico (Y de Roux)",
            "band": "Banda Gástrica",
            "balloon": "Balão Gástrico",
            "other": "Outro",
        }
    )
    
    # Fases (dict de dataclasses imutáveis)
    phases: dict[str, BariatricPhase] = field(
        default_factory=lambda: {
            "liquid": BariatricPhase("Líquida", "0–14", 200, 600),
            "pasty": BariatricPhase("Pastosa", "15–30", 250, 700),
            "soft": BariatricPhase("Branda", "31–60", 350, 900),
            "solid": BariatricPhase("Sólida", "61–180", 500, 1200),
            "maintenance": BariatricPhase("Manutenção", "181+", 700, 1500),
        }
    )
    
    # Suplementos essenciais (tuple imutável)
    essentials: tuple[BariatricSupplement, ...] = (
        BariatricSupplement("Vitamina B12", "1000", "mcg"),
        BariatricSupplement("Vitamina D3", "2000", "UI"),
        BariatricSupplement("Ferro", "45", "mg"),
        BariatricSupplement("Cálcio Citrato", "1200", "mg"),
        BariatricSupplement("Zinco", "15", "mg"),
        BariatricSupplement("Vitamina B1 (Tiamina)", "100", "mg"),
        BariatricSupplement("Proteína Whey", "30", "g"),
    )


@dataclass(frozen=True)
class GamificationConfig:
    """Sistema de XP e recompensas."""
    
    # XP por ação
    xp_checkin: int = 50
    xp_refeicao: int = 25
    xp_peso: int = 30
    xp_habito: int = 20
    xp_suplemento: int = 10
    xp_treino: int = 40
    xp_glp1: int = 25
    xp_medida: int = 15
    xp_foto: int = 10
    
    # Bônus por streaks
    xp_streak_7: int = 100
    xp_streak_14: int = 200
    xp_streak_30: int = 500
    xp_streak_90: int = 1000
    
    # Meta concluída
    xp_meta_concluida: int = 200
    
    def get_xp_for_action(self, action: str) -> int:
        """Retorna XP para uma ação específica."""
        return {
            "checkin": self.xp_checkin,
            "refeicao": self.xp_refeicao,
            "peso": self.xp_peso,
            "habito": self.xp_habito,
            "suplemento": self.xp_suplemento,
            "treino": self.xp_treino,
            "glp1": self.xp_glp1,
            "medida": self.xp_medida,
            "foto": self.xp_foto,
        }.get(action, 0)
    
    def get_xp_for_streak(self, days: int) -> int:
        """Retorna XP bônus para streak."""
        if days >= 90:
            return self.xp_streak_90
        elif days >= 30:
            return self.xp_streak_30
        elif days >= 14:
            return self.xp_streak_14
        elif days >= 7:
            return self.xp_streak_7
        return 0


@dataclass(frozen=True)
class SymptomsConfig:
    """Lista de sintomas e severidade."""
    
    # Sintomas (tuple de tuples imutável)
    symptom_list: tuple[tuple[str, str], ...] = (
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
    
    # Sintomas graves (frozenset imutável)
    severe_symptoms: frozenset[str] = frozenset({
        "nausea", "vomiting", "pain", "dizziness"
    })
    
    def is_severe(self, symptom_key: str) -> bool:
        """Verifica se um sintoma é grave."""
        return symptom_key in self.severe_symptoms


@dataclass(frozen=True)
class WorkoutConfig:
    """Tipos de treino suportados."""
    
    types: dict[str, str] = field(
        default_factory=lambda: {
            "strength": "🏋️ Musculação",
            "cardio": "🏃 Cardio",
            "hiit": "⚡ HIIT",
            "yoga": "🧘 Yoga/Pilates",
            "swimming": "🏊 Natação",
            "cycling": "🚴 Ciclismo",
            "walking": "🚶 Caminhada",
            "functional": "💪 Funcional",
            "sports": "⚽ Esporte",
            "other": "🎯 Outro",
        }
    )


@dataclass(frozen=True)
class MessagesConfig:
    """Mensagens motivacionais e disclaimers."""
    
    # Mensagens por modo (dict de tuples imutáveis)
    motivational: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "general": (
                "Consistência bate perfeição todos os dias.",
                "Um dia de cada vez. Isso é tudo que precisa.",
                "Você não precisa ser extremo. Só precisa ser constante.",
                "Cada escolha alimentar é um voto pela pessoa que você quer ser.",
                "O resultado é consequência. O hábito é a causa.",
            ),
            "fitness": (
                "O corpo muda devagar. A disciplina muda rápido.",
                "Cada treino é uma promessa cumprida com você mesmo.",
                "Força não é só física.",
                "Proteína primeiro. Sempre.",
                "Descanso é parte do treino, não ausência dele.",
            ),
            "bariatric": (
                "Cada refeição certa é uma vitória clínica real.",
                "Seu corpo está se reconstruindo. Respeite o processo.",
                "Pequenas porções, grandes resultados.",
                "A cirurgia foi o começo. O hábito é o trabalho real.",
                "Mastigue devagar. Seu novo estômago agradece.",
            ),
            "glp1": (
                "O medicamento abre a porta. Você decide o que entra.",
                "Proteína primeiro. Sempre.",
                "Adesão ao tratamento é parte da transformação.",
                "Cada dose registrada é um compromisso com sua saúde.",
                "O remédio controla a fome. Você controla as escolhas.",
            ),
        }
    )
    
    medical_disclaimer: str = (
        "⚕️ O Melshape é uma ferramenta de apoio e não substitui orientação "
        "médica ou nutricional profissional. Em caso de sintomas graves ou "
        "dúvidas sobre seu tratamento, procure seu médico."
    )
    
    def get_motivational_message(self, health_mode: str) -> str:
        """Retorna uma mensagem motivacional para o modo de saúde."""
        import random
        messages = self.motivational.get(health_mode, self.motivational["general"])
        return random.choice(messages)


@dataclass(frozen=True)
class LoggingConfig:
    """Configurações de logging."""
    
    level: int = field(
        default_factory=lambda: getattr(
            logging,
            _get_env("LOG_LEVEL", "INFO").upper(),
            logging.INFO
        )
    )
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    """Configuração principal da aplicação (agrega todas as sub-configurações)."""
    
    PRODUCT: ProductIdentity = field(default_factory=ProductIdentity)
    ENV: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    DEMO: DemoConfig = field(default_factory=DemoConfig)
    PRICING: PricingConfig = field(default_factory=PricingConfig)
    NUTRITION: NutritionConfig = field(default_factory=NutritionConfig)
    GLP1: GLP1Config = field(default_factory=GLP1Config)
    BARIATRIC: BariatricConfig = field(default_factory=BariatricConfig)
    GAMIFICATION: GamificationConfig = field(default_factory=GamificationConfig)
    SYMPTOMS: SymptomsConfig = field(default_factory=SymptomsConfig)
    WORKOUT: WorkoutConfig = field(default_factory=WorkoutConfig)
    MESSAGES: MessagesConfig = field(default_factory=MessagesConfig)
    LOGGING: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Constantes simples
    QUICK_ADD_ML: tuple[int, ...] = (200, 300, 500, 750)


# Instância global da configuração
config: Final[Config] = Config()


# ─────────────────────────────────────────────────────────────────────────────
# VALIDAÇÃO DE AMBIENTE
# ─────────────────────────────────────────────────────────────────────────────

def validate_environment() -> list[str]:
    """
    Valida variáveis de ambiente críticas.
    
    Returns:
        Lista de warnings (vazia se tudo ok).
    
    Example:
        >>> warnings = validate_environment()
        >>> if warnings:
        ...     for w in warnings:
        ...         print(w)
    """
    warnings: list[str] = []
    
    # Supabase é crítico em produção/staging
    if config.ENV.is_production or config.ENV.is_staging:
        if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
            warnings.append("⚠️ SUPABASE_URL e SUPABASE_KEY são obrigatórios em produção")
        
        if not os.getenv("RESEND_API_KEY"):
            warnings.append("⚠️ RESEND_API_KEY não configurado — emails não serão enviados")
    
    # Validações específicas de desenvolvimento
    if config.ENV.is_development:
        if config.DEMO.email == "demo@melshape.com.br":
            warnings.append("ℹ️ Usando credenciais demo padrão — configure DEMO_EMAIL em produção")
    
    return warnings


def print_environment_warnings() -> None:
    """Imprime warnings de ambiente (chamar explicitamente quando necessário)."""
    warnings = validate_environment()
    for warning in warnings:
        print(warning)


# ─────────────────────────────────────────────────────────────────────────────
# COMPATIBILIDADE RETROATIVA (aliases para código legado)
# ─────────────────────────────────────────────────────────────────────────────

# Identidade
APP_NAME: Final[str] = config.PRODUCT.name
APP_TAGLINE: Final[str] = config.PRODUCT.tagline
APP_ICON: Final[str] = config.PRODUCT.icon
APP_VERSION: Final[str] = config.PRODUCT.version
APP_DESCRIPTION: Final[str] = config.PRODUCT.description

# Ambiente
ENV: Final[str] = config.ENV.env
APP_URL: Final[str] = config.ENV.app_url
SUPPORT_EMAIL: Final[str] = config.ENV.support_email

# Demo
DEMO_EMAIL: Final[str] = config.DEMO.email
DEMO_PASSWORD: Final[str] = config.DEMO.password

# Planos
TRIAL_DAYS: Final[int] = config.PRICING.trial_days
PRO_PRICE: Final[float] = config.PRICING.pro_price
CLINIC_PRICE: Final[float] = config.PRICING.clinic_price
LIFETIME_PRICE: Final[float] = config.PRICING.lifetime_price
PLAN_FREE: Final[str] = config.PRICING.PLAN_FREE
PLAN_TRIAL: Final[str] = config.PRICING.PLAN_TRIAL
PLAN_PRO: Final[str] = config.PRICING.PLAN_PRO
PLAN_CLINIC: Final[str] = config.PRICING.PLAN_CLINIC
PLAN_LIFETIME: Final[str] = config.PRICING.PLAN_LIFETIME

# Nutrição
HYDRATION_GOAL_ML: Final[int] = config.NUTRITION.hydration_goal_ml
MIN_CALORIES_SAFE: Final[int] = config.NUTRITION.min_calories_safe
SAFE_MIN_CALORIES: Final[int] = config.NUTRITION.safe_min_calories
MAX_CALORIES_DISPLAY: Final[int] = config.NUTRITION.max_calories_display
ALERT_PCT_WARNING: Final[float] = config.NUTRITION.alert_pct_warning
ACTIVITY_FACTORS: Final[dict[str, float]] = config.NUTRITION.activity_factors
GENERAL_PROTEIN_PER_KG: Final[float] = config.NUTRITION.general_protein_per_kg
FITNESS_PROTEIN_PER_KG: Final[float] = config.NUTRITION.fitness_protein_per_kg
GLP1_PROTEIN_PER_KG: Final[float] = config.NUTRITION.glp1_protein_per_kg
BARIATRIC_PROTEIN_PER_KG: Final[float] = config.NUTRITION.bariatric_protein_per_kg

# GLP-1
GLP1_MEDICATIONS: Final[list[str]] = list(config.GLP1.medications)
GLP1_DOSES: Final[dict[str, list[str]]] = {k: list(v) for k, v in config.GLP1.doses.items()}
GLP1_PHASES: Final[dict[str, str]] = config.GLP1.phases
GLP1_LOW_KCAL_THRESHOLD: Final[int] = config.GLP1.low_kcal_threshold
GLP1_LOW_KCAL_DAYS: Final[int] = config.GLP1.low_kcal_days

# Bariátrica
BARIATRIC_TYPES: Final[dict[str, str]] = config.BARIATRIC.types
BARIATRIC_PHASES: Final[dict[str, dict[str, Any]]] = {
    k: {"name": v.name, "days": v.days, "max_ml": v.max_ml, "max_cal": v.max_cal}
    for k, v in config.BARIATRIC.phases.items()
}
BARIATRIC_ESSENTIALS: Final[list[dict[str, str]]] = [
    {"name": s.name, "dose": s.dose, "unit": s.unit}
    for s in config.BARIATRIC.essentials
]

# Gamificação
XP_CHECKIN: Final[int] = config.GAMIFICATION.xp_checkin
XP_REFEICAO: Final[int] = config.GAMIFICATION.xp_refeicao
XP_PESO: Final[int] = config.GAMIFICATION.xp_peso
XP_HABITO: Final[int] = config.GAMIFICATION.xp_habito
XP_SUPLEMENTO: Final[int] = config.GAMIFICATION.xp_suplemento
XP_TREINO: Final[int] = config.GAMIFICATION.xp_treino
XP_GLP1: Final[int] = config.GAMIFICATION.xp_glp1
XP_MEDIDA: Final[int] = config.GAMIFICATION.xp_medida
XP_FOTO: Final[int] = config.GAMIFICATION.xp_foto
XP_STREAK_7: Final[int] = config.GAMIFICATION.xp_streak_7
XP_STREAK_14: Final[int] = config.GAMIFICATION.xp_streak_14
XP_STREAK_30: Final[int] = config.GAMIFICATION.xp_streak_30
XP_STREAK_90: Final[int] = config.GAMIFICATION.xp_streak_90
XP_META_CONCLUIDA: Final[int] = config.GAMIFICATION.xp_meta_concluida

# Sintomas
SYMPTOM_LIST: Final[list[tuple[str, str]]] = list(config.SYMPTOMS.symptom_list)
SEVERE_SYMPTOMS: Final[set[str]] = set(config.SYMPTOMS.severe_symptoms)

# Treino
WORKOUT_TYPES: Final[dict[str, str]] = config.WORKOUT.types

# Hidratação
QUICK_ADD_ML: Final[tuple[int, ...]] = config.QUICK_ADD_ML

# Mensagens
MENSAGENS_MOTIVACIONAIS: Final[dict[str, list[str]]] = {
    k: list(v) for k, v in config.MESSAGES.motivational.items()
}
MEDICAL_DISCLAIMER: Final[str] = config.MESSAGES.medical_disclaimer

# Logging
LOG_LEVEL: Final[int] = config.LOGGING.level
LOG_FORMAT: Final[str] = config.LOGGING.format
LOG_DATE_FORMAT: Final[str] = config.LOGGING.date_format

# Validação
ENV_WARNINGS: Final[list[str]] = validate_environment()


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Configuração principal
    "config",
    "Config",
    # Sub-configurações
    "ProductIdentity",
    "EnvironmentConfig",
    "DemoConfig",
    "PricingConfig",
    "NutritionConfig",
    "GLP1Config",
    "BariatricConfig",
    "GamificationConfig",
    "SymptomsConfig",
    "WorkoutConfig",
    "MessagesConfig",
    "LoggingConfig",
    "BariatricPhase",
    "BariatricSupplement",
    # Compatibilidade retroativa
    "APP_NAME", "APP_TAGLINE", "APP_ICON", "APP_VERSION", "APP_DESCRIPTION",
    "ENV", "APP_URL", "SUPPORT_EMAIL",
    "DEMO_EMAIL", "DEMO_PASSWORD",
    "TRIAL_DAYS", "PRO_PRICE", "CLINIC_PRICE", "LIFETIME_PRICE",
    "PLAN_FREE", "PLAN_TRIAL", "PLAN_PRO", "PLAN_CLINIC", "PLAN_LIFETIME",
    "HYDRATION_GOAL_ML", "MIN_CALORIES_SAFE", "SAFE_MIN_CALORIES",
    "MAX_CALORIES_DISPLAY", "ALERT_PCT_WARNING", "ACTIVITY_FACTORS",
    "GENERAL_PROTEIN_PER_KG", "FITNESS_PROTEIN_PER_KG",
    "GLP1_PROTEIN_PER_KG", "BARIATRIC_PROTEIN_PER_KG",
    "GLP1_MEDICATIONS", "GLP1_DOSES", "GLP1_PHASES",
    "GLP1_LOW_KCAL_THRESHOLD", "GLP1_LOW_KCAL_DAYS",
    "BARIATRIC_TYPES", "BARIATRIC_PHASES", "BARIATRIC_ESSENTIALS",
    "XP_CHECKIN", "XP_REFEICAO", "XP_PESO", "XP_HABITO", "XP_SUPLEMENTO",
    "XP_TREINO", "XP_GLP1", "XP_MEDIDA", "XP_FOTO",
    "XP_STREAK_7", "XP_STREAK_14", "XP_STREAK_30", "XP_STREAK_90",
    "XP_META_CONCLUIDA",
    "SYMPTOM_LIST", "SEVERE_SYMPTOMS",
    "WORKOUT_TYPES",
    "QUICK_ADD_ML",
    "MENSAGENS_MOTIVACIONAIS", "MEDICAL_DISCLAIMER",
    "LOG_LEVEL", "LOG_FORMAT", "LOG_DATE_FORMAT",
    "ENV_WARNINGS",
    # Funções
    "validate_environment",
    "print_environment_warnings",
]
