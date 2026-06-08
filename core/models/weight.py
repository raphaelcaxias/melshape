"""Melshape — Modelo de pesagem."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class WeightLog:
    weight:      float
    log_date:    str   = field(default_factory=lambda: date.today().isoformat())
    notes:       str   = ""
    body_fat:    float = 0.0
    muscle_mass: float = 0.0
    user_id:     str   = ""

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
