"""Melshape — Gamificação: streaks, conquistas, XP, níveis."""
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any

from core.database import Database

logger = logging.getLogger("Melshape.Gamification")

ACHIEVEMENTS = [
    {"name": "first_meal",       "title": "🍽️ Primeira Refeição",       "desc": "Registrou a primeira refeição!",              "xp": 50},
    {"name": "ten_meals",        "title": "🍴 10 Refeições",             "desc": "10 refeições registradas!",                   "xp": 100},
    {"name": "fifty_meals",      "title": "🎖️ 50 Refeições",            "desc": "Mestre do registro!",                         "xp": 500},
    {"name": "week_streak",      "title": "📅 7 Dias Seguidos",          "desc": "Uma semana de consistência!",                 "xp": 200},
    {"name": "month_streak",     "title": "🏆 30 Dias!",                 "desc": "30 dias consecutivos. Incrível!",             "xp": 1000},
    {"name": "first_weight",     "title": "⚖️ Primeira Pesagem",         "desc": "Começou a monitorar o peso!",                 "xp": 50},
    {"name": "lost_1kg",         "title": "📉 Perdeu 1 kg",              "desc": "1 kg eliminado!",                             "xp": 300},
    {"name": "lost_5kg",         "title": "💪 Perdeu 5 kg",              "desc": "5 kg eliminados!",                            "xp": 1000},
    {"name": "first_workout",    "title": "🏋️ Primeiro Treino",          "desc": "Registrou o primeiro treino!",                "xp": 50},
    {"name": "first_supplement", "title": "💊 Suplementação",             "desc": "Registrou suplementos pela primeira vez!",    "xp": 50},
    {"name": "hydration_goal",   "title": "💧 Hidratação em Dia",         "desc": "Atingiu a meta de água hoje!",                "xp": 30},
    {"name": "glp1_week",        "title": "💉 1 Semana GLP-1",           "desc": "Uma semana de tratamento monitorado!",        "xp": 150},
    {"name": "bariatric_month",  "title": "🔪 1 Mês Pós-Cirurgia",       "desc": "Um mês de acompanhamento bariátrico!",        "xp": 500},
    {"name": "first_sleep",      "title": "😴 Sono Registrado",          "desc": "Começou a monitorar o sono!",                 "xp": 30},
]

LEVELS = [
    {"level": 1, "name": "Iniciante",   "min_xp": 0,    "icon": "🌱"},
    {"level": 2, "name": "Determinado", "min_xp": 200,  "icon": "🌿"},
    {"level": 3, "name": "Consistente", "min_xp": 500,  "icon": "🌳"},
    {"level": 4, "name": "Dedicado",    "min_xp": 1000, "icon": "⭐"},
    {"level": 5, "name": "Campeão",     "min_xp": 2000, "icon": "🏆"},
    {"level": 6, "name": "Lendário",    "min_xp": 5000, "icon": "👑"},
]

WEEKLY_CHALLENGES = [
    {"title": "Registrar 14 refeições esta semana",  "xp": 50,  "emoji": "🍴"},
    {"title": "Atingir meta proteica por 3 dias",    "xp": 120, "emoji": "🥩"},
    {"title": "Beber 2L de água por 5 dias",         "xp": 80,  "emoji": "💧"},
    {"title": "Pesar-se 2 vezes esta semana",        "xp": 80,  "emoji": "⚖️"},
    {"title": "Registrar treino por 3 dias",         "xp": 100, "emoji": "🏋️"},
    {"title": "Tomar suplementos por 5 dias",        "xp": 90,  "emoji": "💊"},
    {"title": "Registrar sono por 5 dias seguidos",  "xp": 70,  "emoji": "😴"},
]


class GamificationService:

    def __init__(self, db: Database):
        self.db = db

    def streak(self) -> int:
        meals = self.db.get_meals(60)
        if not meals:
            return 0
        dates = sorted(set(
            datetime.strptime(m.meal_date, "%Y-%m-%d").date()
            for m in meals
        ))
        today = date.today()
        if dates[-1] not in [today, today - timedelta(days=1)]:
            return 0
        count = 1
        for i in range(len(dates) - 1, 0, -1):
            if (dates[i] - dates[i - 1]).days == 1:
                count += 1
            else:
                break
        return count

    def total_xp(self) -> int:
        earned = {a.get("achievement_name") for a in self.db.get_achievements()}
        return sum(a["xp"] for a in ACHIEVEMENTS if a["name"] in earned)

    def level(self) -> Dict[str, Any]:
        xp      = self.total_xp()
        current = LEVELS[0]
        for lvl in LEVELS:
            if xp >= lvl["min_xp"]:
                current = lvl
        idx = LEVELS.index(current)
        nxt = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None
        pct = (
            int((xp - current["min_xp"]) / (nxt["min_xp"] - current["min_xp"]) * 100)
            if nxt else 100
        )
        return {"xp": xp, "current": current, "next": nxt, "progress_pct": pct}

    def check_achievements(self, user: dict = None) -> List[str]:
        unlocked    = []
        meals       = self.db.get_meals(365)
        weights     = self.db.get_weights(365)
        workouts    = self.db.get_workouts(365)
        supplements = self.db.get_supplements(365)
        sleep_logs  = self.db.get_sleep_logs(365)
        streak      = self.streak()

        checks = [
            ("first_meal",       "🍽️ Primeira Refeição",   len(meals) >= 1),
            ("ten_meals",        "🍴 10 Refeições",         len(meals) >= 10),
            ("fifty_meals",      "🎖️ 50 Refeições",        len(meals) >= 50),
            ("week_streak",      "📅 7 Dias Seguidos",      streak >= 7),
            ("month_streak",     "🏆 30 Dias!",             streak >= 30),
            ("first_workout",    "🏋️ Primeiro Treino",      len(workouts) >= 1),
            ("first_supplement", "💊 Suplementação",        len(supplements) >= 1),
            ("first_sleep",      "😴 Sono Registrado",      len(sleep_logs) >= 1),
        ]

        if not weights.empty:
            checks.append(("first_weight", "⚖️ Primeira Pesagem", True))
            if len(weights) >= 2:
                diff = float(weights.iloc[0]["weight"]) - float(weights.iloc[-1]["weight"])
                checks.append(("lost_1kg", "📉 Perdeu 1 kg", diff >= 1.0))
                checks.append(("lost_5kg", "💪 Perdeu 5 kg", diff >= 5.0))

        if user:
            if user.get("uses_glp1") and user.get("glp1_start_date"):
                try:
                    start = datetime.strptime(user["glp1_start_date"], "%Y-%m-%d").date()
                    checks.append(("glp1_week", "💉 1 Semana GLP-1", (date.today() - start).days >= 7))
                except Exception:
                    pass

        for name, title, condition in checks:
            if condition and self.db.unlock_achievement(name, title):
                unlocked.append(title)

        return unlocked

    def weekly_challenges(self) -> List[Dict[str, Any]]:
        week  = date.today().isocalendar()[1]
        start = week % len(WEEKLY_CHALLENGES)
        return (WEEKLY_CHALLENGES[start:] + WEEKLY_CHALLENGES[:start])[:3]
