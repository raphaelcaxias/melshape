"""Melshape — Helpers de data e período."""
from datetime import datetime


def get_greeting(name: str) -> str:
    h = datetime.now().hour
    if h < 12:
        return f"☀️ Bom dia, {name}!"
    if h < 18:
        return f"🌤️ Boa tarde, {name}!"
    return f"🌙 Boa noite, {name}!"


def detect_meal_period(hour: int) -> str:
    if 5  <= hour < 10: return "Café da Manhã"
    if 10 <= hour < 14: return "Almoço"
    if 14 <= hour < 18: return "Lanche da Tarde"
    if 18 <= hour < 21: return "Jantar"
    return "Ceia"


def detect_meal_type(hour: int) -> str:
    if 5  <= hour < 10: return "cafe_manha"
    if 10 <= hour < 14: return "almoco"
    if 14 <= hour < 18: return "lanche"
    if 18 <= hour < 21: return "jantar"
    return "ceia"
