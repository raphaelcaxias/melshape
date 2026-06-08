"""Melshape — Modelo de profissional de saúde."""
from dataclasses import dataclass
from typing import Optional
import config


@dataclass
class Professional:
    email:            str
    name:             str
    password_hash:    str  = ""
    user_type:        str  = "professional"
    specialty:        str  = "nutritionist"
    crn_number:       str  = ""
    crn_state:        str  = ""
    clinic_name:      str  = ""
    phone:            str  = ""
    pro_plan:         str  = "starter"
    patient_count:    int  = 0
    trial_expires_at: Optional[str] = None
    lgpd_accepted_at: Optional[str] = None
    onboarding_done:  bool = False

    def max_patients(self) -> int:
        return config.PRO_PLAN_LIMITS.get(self.pro_plan, {}).get("patients", 15)

    def can_add_patient(self) -> bool:
        return self.patient_count < self.max_patients()

    def specialty_label(self) -> str:
        return {
            "nutritionist":    "🥗 Nutricionista",
            "endocrinologist": "🩺 Endocrinologista",
            "other":           "👨‍⚕️ Profissional de Saúde",
        }.get(self.specialty, "Profissional")

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, d: dict) -> "Professional":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)
