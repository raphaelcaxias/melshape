"""Melshape — Modelo de treino."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class WorkoutLog:
    workout_type:    str  = "rest"
    muscle_group:    str  = ""
    intensity:       str  = "moderate"
    duration_min:    int  = 0
    calories_burned: int  = 0
    log_date:        str  = field(default_factory=lambda: date.today().isoformat())
    notes:           str  = ""
    user_id:         str  = ""

    def calorie_adjustment(self) -> int:
        if self.workout_type == "rest":
            return -100
        base = {"cardio": 150, "strength": 200, "hiit": 300, "mixed": 250}.get(self.workout_type, 0)
        mult = {"light": 0.7, "moderate": 1.0, "heavy": 1.4}.get(self.intensity, 1.0)
        return int(base * mult)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


WORKOUT_TYPES = {
    "rest":     "😴 Descanso",
    "cardio":   "🏃 Cardio",
    "strength": "🏋️ Musculação",
    "hiit":     "⚡ HIIT",
    "mixed":    "🔄 Misto",
}

MUSCLE_GROUPS = {
    "":          "Não especificado",
    "chest":     "Peito",
    "back":      "Costas",
    "legs":      "Pernas",
    "shoulders": "Ombros",
    "arms":      "Braços",
    "core":      "Core / Abdômen",
    "full":      "Corpo Inteiro",
}
