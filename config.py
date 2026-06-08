"""
Melshape v2.0 — Configurações globais, constantes e feature flags.
"""
import os
from datetime import timedelta

# ── IDENTIDADE ────────────────────────────────────────────────────────────────
APP_NAME     = "Melshape"
APP_VERSION  = "2.0.0"
APP_ICON     = "🔥"
APP_TAGLINE  = "Para quem está mudando de verdade."
APP_URL      = "https://melshape.com.br"

MEDICAL_DISCLAIMER = (
    "⚕️ *O Melshape é uma ferramenta de apoio ao monitoramento nutricional. "
    "Não substitui orientação médica ou nutricional profissional.*"
)

# ── SUPABASE ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ── DEMO ──────────────────────────────────────────────────────────────────────
DEMO_EMAIL    = "demo@melshape.com.br"
DEMO_PASSWORD = "demo1234"
DEMO_NAME     = "Ana Demo"

# ── TRIAL ─────────────────────────────────────────────────────────────────────
TRIAL_DAYS             = 10
TRIAL_ALERT_DAYS       = 3   # alerta quando restam X dias

# ── LIMITES POR PLANO (paciente) ──────────────────────────────────────────────
PLAN_LIMITS: dict = {
    "free": {
        "meals_per_day":  3,
        "history_days":   7,
        "charts":         False,
        "export":         False,
        "bariatric_mode": False,
        "glp1_mode":      False,
        "supplements":    False,
        "workout":        False,
        "hydration":      False,
        "sleep":          False,
    },
    "essencial": {
        "meals_per_day":  999,
        "history_days":   90,
        "charts":         True,
        "export":         False,
        "bariatric_mode": False,
        "glp1_mode":      True,
        "supplements":    True,
        "workout":        False,
        "hydration":      True,
        "sleep":          False,
    },
    "pro": {
        "meals_per_day":  999,
        "history_days":   365,
        "charts":         True,
        "export":         True,
        "bariatric_mode": True,
        "glp1_mode":      True,
        "supplements":    True,
        "workout":        True,
        "hydration":      True,
        "sleep":          True,
    },
    "trial": {
        "meals_per_day":  999,
        "history_days":   365,
        "charts":         True,
        "export":         True,
        "bariatric_mode": True,
        "glp1_mode":      True,
        "supplements":    True,
        "workout":        True,
        "hydration":      True,
        "sleep":          True,
    },
    "lifetime": {
        "meals_per_day":  999,
        "history_days":   365,
        "charts":         True,
        "export":         True,
        "bariatric_mode": True,
        "glp1_mode":      True,
        "supplements":    True,
        "workout":        True,
        "hydration":      True,
        "sleep":          True,
    },
}

# ── PLANOS PROFISSIONAL ───────────────────────────────────────────────────────
PRO_PLAN_LIMITS: dict = {
    "starter":    {"patients": 15,   "price": 39.90},
    "solo":       {"patients": 50,   "price": 69.90},
    "clinica":    {"patients": 150,  "price": 129.90},
    "pro":        {"patients": 400,  "price": 199.90},
    "enterprise": {"patients": 9999, "price": 349.90},
}

# ── PREÇOS PACIENTE ───────────────────────────────────────────────────────────
PATIENT_PRICES: dict = {
    "essencial": {"monthly": 9.90,  "annual": 95.00},
    "pro":       {"monthly": 19.90, "annual": 159.00},
    "lifetime":  {"once": 197.00},
}

# ── NUTRIÇÃO ──────────────────────────────────────────────────────────────────
MIN_CALORIES_SAFE      = 800    # abaixo → alerta severo
SAFE_MIN_CALORIES      = 1200
ALERT_PCT_WARNING      = 0.85
ALERT_PCT_DANGER       = 1.0

GLP1_PROTEIN_PER_KG      = 1.6
BARIATRIC_PROTEIN_PER_KG = 1.5
FITNESS_PROTEIN_PER_KG   = 2.0
GENERAL_PROTEIN_PER_KG   = 1.4

HYDRATION_MIN_ML         = 1500   # mínimo diário
HYDRATION_GOAL_ML        = 2000   # meta padrão

# Alerta GLP-1: <900kcal por 3 dias consecutivos
GLP1_LOW_KCAL_THRESHOLD  = 900
GLP1_LOW_KCAL_DAYS       = 3

# ── ATIVIDADE ─────────────────────────────────────────────────────────────────
ACTIVITY_FACTORS: dict = {
    "sedentary":   1.2,
    "light":       1.375,
    "moderate":    1.55,
    "active":      1.725,
    "very_active": 1.9,
}

ACTIVITY_LABELS: dict = {
    "sedentary":   "🛋️ Sedentário (sem exercício)",
    "light":       "🚶 Leve (1-3x/semana)",
    "moderate":    "🏃 Moderado (3-5x/semana)",
    "active":      "💪 Ativo (6-7x/semana)",
    "very_active": "🏋️ Muito Ativo (2x/dia)",
}

# ── GLP-1 ─────────────────────────────────────────────────────────────────────
GLP1_MEDICATIONS: list = [
    "Ozempic (Semaglutida)",
    "Wegovy (Semaglutida)",
    "Mounjaro (Tirzepatida)",
    "Zepbound (Tirzepatida)",
    "Victoza (Liraglutida)",
    "Saxenda (Liraglutida)",
    "Outro",
]

GLP1_DOSES: dict = {
    "Ozempic (Semaglutida)":  ["0.25mg", "0.5mg", "1.0mg", "2.0mg"],
    "Wegovy (Semaglutida)":   ["0.25mg", "0.5mg", "1.0mg", "1.7mg", "2.4mg"],
    "Mounjaro (Tirzepatida)": ["2.5mg", "5mg", "7.5mg", "10mg", "12.5mg", "15mg"],
    "Zepbound (Tirzepatida)": ["2.5mg", "5mg", "7.5mg", "10mg", "12.5mg", "15mg"],
    "Victoza (Liraglutida)":  ["0.6mg", "1.2mg", "1.8mg"],
    "Saxenda (Liraglutida)":  ["0.6mg", "1.2mg", "1.8mg", "2.4mg", "3.0mg"],
    "Outro":                  ["Personalizado"],
}

GLP1_PHASES: dict = {
    "adapting":    "Adaptação",
    "maintenance": "Manutenção",
    "tapering":    "Desmame",
    "stopped":     "Parado",
}

# ── BARIÁTRICO ────────────────────────────────────────────────────────────────
BARIATRIC_PHASES: dict = {
    "liquid":      {"name": "Líquida",       "days": "1-14",   "max_ml": 200,  "max_cal": 600},
    "pasty":       {"name": "Pastosa",        "days": "15-30",  "max_ml": 300,  "max_cal": 800},
    "soft":        {"name": "Branda",         "days": "31-60",  "max_ml": 400,  "max_cal": 1000},
    "solid":       {"name": "Sólida",         "days": "61-180", "max_ml": 500,  "max_cal": 1200},
    "maintenance": {"name": "Manutenção",     "days": "180+",   "max_ml": 600,  "max_cal": 1400},
}

BARIATRIC_TYPES: dict = {
    "sleeve":  "Sleeve (Gastrectomia Vertical)",
    "bypass":  "Bypass Gástrico (Roux-en-Y)",
    "band":    "Banda Gástrica",
    "other":   "Outro",
}

# ── SONO ──────────────────────────────────────────────────────────────────────
SLEEP_MIN_HOURS = 6.0
SLEEP_GOAL_HOURS = 8.0

# ── LOGGING ───────────────────────────────────────────────────────────────────
LOG_LEVEL  = "INFO"
LOG_FORMAT = "%(asctime)s · %(name)s · %(levelname)s · %(message)s"
