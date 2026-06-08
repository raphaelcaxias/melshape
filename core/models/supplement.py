"""Melshape — Modelo de suplemento."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Supplement:
    name:       str
    dose:       str  = ""
    unit:       str  = "mg"
    category:   str  = "vitamin"
    time_taken: str  = ""
    log_date:   str  = field(default_factory=lambda: date.today().isoformat())
    notes:      str  = ""
    user_id:    str  = ""

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


BARIATRIC_ESSENTIALS = [
    {"name": "Vitamina B12",         "dose": "1000", "unit": "mcg", "category": "vitamin"},
    {"name": "Vitamina D3",          "dose": "3000", "unit": "UI",  "category": "vitamin"},
    {"name": "Vitamina B1 (Tiamina)","dose": "100",  "unit": "mg",  "category": "vitamin"},
    {"name": "Ferro",                "dose": "40",   "unit": "mg",  "category": "mineral"},
    {"name": "Cálcio Citrato",       "dose": "1200", "unit": "mg",  "category": "mineral"},
    {"name": "Zinco",                "dose": "15",   "unit": "mg",  "category": "mineral"},
    {"name": "Ácido Fólico",         "dose": "400",  "unit": "mcg", "category": "vitamin"},
    {"name": "Proteína Whey",        "dose": "30",   "unit": "g",   "category": "protein"},
]

GLP1_COMMON = [
    {"name": "Proteína Whey", "dose": "30",   "unit": "g",   "category": "protein"},
    {"name": "Creatina",      "dose": "5",    "unit": "g",   "category": "protein"},
    {"name": "Vitamina D3",   "dose": "2000", "unit": "UI",  "category": "vitamin"},
    {"name": "Magnésio",      "dose": "300",  "unit": "mg",  "category": "mineral"},
    {"name": "Ômega-3",       "dose": "2",    "unit": "g",   "category": "other"},
    {"name": "Vitamina B12",  "dose": "500",  "unit": "mcg", "category": "vitamin"},
]
