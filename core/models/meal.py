"""Melshape — Modelo de refeição."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Meal:
    food:           str
    calories:       int
    protein:        float = 0.0
    carbs:          float = 0.0
    fat:            float = 0.0
    fiber:          float = 0.0
    quantity:       float = 1.0
    volume_ml:      float = 0.0      # para controle bariátrico
    meal_time:      str   = ""
    meal_date:      str   = field(default_factory=lambda: date.today().isoformat())
    meal_type:      str   = ""
    mood:           str   = ""
    notes:          str   = ""
    nutrient_score: int   = 0
    user_id:        str   = ""

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
