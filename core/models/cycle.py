"""Melshape — Modelo de ciclo menstrual."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class CycleLog:
    phase:      str   = "follicular"  # menstrual | follicular | ovulation | luteal
    symptoms:   list  = field(default_factory=list)
    log_date:   str   = field(default_factory=lambda: date.today().isoformat())
    notes:      str   = ""
    user_id:    str   = ""

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


CYCLE_PHASES = {
    "menstrual":    ("🔴", "Menstrual",   "Período menstrual"),
    "follicular":   ("🟡", "Folicular",   "Pós-menstrual, pré-ovulação"),
    "ovulation":    ("🟢", "Ovulação",    "Período fértil"),
    "luteal":       ("🟠", "Lútea",       "Pré-menstrual"),
}

CYCLE_SYMPTOMS = [
    ("cramps",    "😣 Cólica"),
    ("bloating",  "🫃 Inchaço"),
    ("mood",      "😔 Alteração de humor"),
    ("cravings",  "🍫 Desejo por doces"),
    ("fatigue",   "😴 Fadiga"),
    ("headache",  "🤕 Dor de cabeça"),
]

# Nota clínica: fase lútea + ganho >0.5kg → aviso de retenção hídrica
LUTEAL_WEIGHT_THRESHOLD = 0.5
