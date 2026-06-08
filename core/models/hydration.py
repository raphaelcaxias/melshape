"""Melshape — Modelo de hidratação (novo)."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class HydrationLog:
    amount_ml: int   = 200
    log_date:  str   = field(default_factory=lambda: date.today().isoformat())
    log_time:  str   = ""
    source:    str   = "water"  # water | juice | tea | other
    user_id:   str   = ""

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


HYDRATION_SOURCES = {
    "water": "💧 Água",
    "juice": "🍊 Suco natural",
    "tea":   "🍵 Chá",
    "other": "🥤 Outro",
}

QUICK_ADD_ML = [150, 200, 300, 500]
