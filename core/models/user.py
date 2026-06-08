"""Melshape — Modelo de usuário (paciente)."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional
import config


@dataclass
class User:
    email:               str
    name:                str
    password_hash:       str  = ""
    user_type:           str  = "patient"

    # Plano & trial
    plan:                str  = "trial"
    trial_started_at:    Optional[str] = None
    trial_expires_at:    Optional[str] = None
    lgpd_accepted_at:    Optional[str] = None

    # Dados pessoais
    gender:              str  = "female"
    age:                 Optional[int]   = None
    height:              Optional[int]   = None
    current_weight:      Optional[float] = None
    goal_weight:         Optional[float] = None
    activity_level:      str  = "moderate"
    goal:                str  = "lose"

    # Modo de saúde
    health_mode:         str  = "general"

    # Bariátrico
    is_bariatric:        bool = False
    surgery_date:        Optional[str] = None
    bariatric_type:      str  = ""
    bariatric_phase:     str  = ""

    # GLP-1
    uses_glp1:           bool = False
    glp1_medication:     str  = ""
    glp1_dose:           str  = ""
    glp1_start_date:     Optional[str] = None
    glp1_phase:          str  = "adapting"

    # Nutrição personalizada
    protein_goal_per_kg: float = 1.6
    custom_calorie_goal: Optional[int] = None

    # Preferências
    dark_mode:           bool = False
    onboarding_done:     bool = False
    professional_id:     Optional[str] = None

    # ── MÉTODOS ──────────────────────────────────────────────────────────────

    def effective_plan(self) -> str:
        if self.plan == "trial":
            if self.trial_expires_at:
                try:
                    exp = datetime.fromisoformat(self.trial_expires_at).date()
                    if date.today() <= exp:
                        return "trial"
                except Exception:
                    pass
            return "free"
        return self.plan

    def trial_days_remaining(self) -> int:
        if not self.trial_expires_at:
            return 0
        try:
            exp = datetime.fromisoformat(self.trial_expires_at).date()
            return max(0, (exp - date.today()).days)
        except Exception:
            return 0

    def can_use(self, feature: str) -> bool:
        plan   = self.effective_plan()
        limits = config.PLAN_LIMITS.get(plan, config.PLAN_LIMITS["free"])
        return bool(limits.get(feature, False))

    def meals_limit_today(self) -> int:
        plan = self.effective_plan()
        return config.PLAN_LIMITS.get(plan, config.PLAN_LIMITS["free"]).get("meals_per_day", 3)

    def bariatric_days_since_surgery(self) -> Optional[int]:
        if not self.surgery_date:
            return None
        try:
            s = datetime.strptime(self.surgery_date, "%Y-%m-%d").date()
            return (date.today() - s).days
        except Exception:
            return None

    def display_health_mode(self) -> str:
        return {
            "general":   "⚖️ Emagrecimento",
            "bariatric": "🔪 Pós-Bariátrica",
            "glp1":      "💉 GLP-1 / Canetas",
            "fitness":   "💪 Fitness",
        }.get(self.health_mode, "⚖️ Geral")

    def to_dict(self) -> dict:
        return {f: getattr(self, f) for f in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)
