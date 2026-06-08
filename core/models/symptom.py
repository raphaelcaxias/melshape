"""Melshape — Modelo de sintoma (GLP-1 / bariátrico)."""
from dataclasses import dataclass, field
from datetime import date


SYMPTOM_LIST = [
    ("nausea",       "🤢 Náusea"),
    ("constipation", "😣 Constipação"),
    ("fatigue",      "😴 Fadiga intensa"),
    ("heartburn",    "🔥 Azia / refluxo"),
    ("dizziness",    "😵 Tontura"),
    ("hair_loss",    "💇 Queda de cabelo"),
    ("pain",         "😟 Dor abdominal"),
]

SEVERE_SYMPTOMS = {"nausea", "dizziness", "pain"}


@dataclass
class SymptomLog:
    symptoms:   list  = field(default_factory=list)   # lista de códigos
    severity:   int   = 1                              # 1-3
    log_date:   str   = field(default_factory=lambda: date.today().isoformat())
    notes:      str   = ""
    user_id:    str   = ""

    def has_severe(self) -> bool:
        return any(s in SEVERE_SYMPTOMS for s in self.symptoms)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
