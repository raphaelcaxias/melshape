"""Melshape — Modelo de sono."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class SleepLog:
    hours:      float = 7.0
    quality:    int   = 3     # 1-5
    log_date:   str   = field(default_factory=lambda: date.today().isoformat())
    notes:      str   = ""
    user_id:    str   = ""

    def is_short(self) -> bool:
        return self.hours < 6.0

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


SLEEP_QUALITY_LABELS = {
    1: "😖 Péssimo",
    2: "😕 Ruim",
    3: "😐 Regular",
    4: "🙂 Bom",
    5: "😄 Ótimo",
}
