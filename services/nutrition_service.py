"""
Melshape — Serviço de nutrição.
TMB/TDEE, metas calóricas, proteína, alertas clínicos, score nutricional.
"""
import logging
import pandas as pd
from datetime import date, timedelta
from typing import Dict, Any, Optional, List

from core.database import Database
from core.models import Meal
import config

logger = logging.getLogger("Melshape.Nutrition")


class NutritionService:

    def __init__(self, db: Database):
        self.db = db

    # ── CÁLCULOS BASE ─────────────────────────────────────────────────────────
    def calc_tmb(self, weight: Optional[float], height: Optional[int],
                 age: Optional[int], gender: str = "female") -> int:
        """Fórmula Mifflin-St Jeor — diferente por gênero."""
        if not all([weight, height, age]):
            return 1500
        base = 10 * weight + 6.25 * height - 5 * age
        return int(base + 5) if gender == "male" else int(base - 161)

    def calc_tdee(self, tmb: int, activity_level: str = "moderate") -> int:
        factor = config.ACTIVITY_FACTORS.get(activity_level, 1.55)
        return int(tmb * factor)

    def calc_goal_calories(self, tmb: int, activity_level: str = "moderate",
                            goal: str = "lose", health_mode: str = "general",
                            workout_adjustment: int = 0) -> int:
        tdee = self.calc_tdee(tmb, activity_level)
        if health_mode == "bariatric":
            base = max(config.MIN_CALORIES_SAFE, tdee - 300)
        elif health_mode == "glp1":
            base = max(config.MIN_CALORIES_SAFE, tdee - 400)
        elif goal == "lose":
            base = max(config.SAFE_MIN_CALORIES, tdee - 500)
        elif goal == "gain":
            base = tdee + 300
        else:
            base = tdee
        return base + workout_adjustment

    def calc_protein_goal(self, weight: Optional[float],
                           health_mode: str = "general") -> float:
        if not weight:
            return 120.0
        per_kg = {
            "glp1":      config.GLP1_PROTEIN_PER_KG,
            "bariatric": config.BARIATRIC_PROTEIN_PER_KG,
            "fitness":   config.FITNESS_PROTEIN_PER_KG,
            "general":   config.GENERAL_PROTEIN_PER_KG,
        }.get(health_mode, config.GENERAL_PROTEIN_PER_KG)
        return round(weight * per_kg, 1)

    def calc_macros_goal(self, goal_calories: int, goal: str = "lose") -> Dict[str, int]:
        if goal == "lose":
            return {
                "protein": int(goal_calories * 0.30 / 4),
                "carbs":   int(goal_calories * 0.35 / 4),
                "fat":     int(goal_calories * 0.35 / 9),
            }
        elif goal == "gain":
            return {
                "protein": int(goal_calories * 0.25 / 4),
                "carbs":   int(goal_calories * 0.50 / 4),
                "fat":     int(goal_calories * 0.25 / 9),
            }
        return {
            "protein": int(goal_calories * 0.25 / 4),
            "carbs":   int(goal_calories * 0.45 / 4),
            "fat":     int(goal_calories * 0.30 / 9),
        }

    def days_to_goal(self, current: Optional[float],
                     goal_w: Optional[float]) -> Optional[int]:
        if not current or not goal_w or current == goal_w:
            return None
        diff  = abs(current - goal_w)
        weeks = diff / (3500 / 7700)
        return int(weeks * 7)

    # ── RESUMOS ───────────────────────────────────────────────────────────────
    def daily_summary(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        if not date_str:
            date_str = date.today().isoformat()
        meals = self.db.get_meals_by_date(date_str)
        return {
            "calories": sum(m.calories for m in meals),
            "protein":  round(sum(m.protein for m in meals), 1),
            "carbs":    round(sum(m.carbs   for m in meals), 1),
            "fat":      round(sum(m.fat     for m in meals), 1),
            "fiber":    round(sum(m.fiber   for m in meals), 1),
            "volume_ml":round(sum(m.volume_ml for m in meals), 0),
            "count":    len(meals),
            "meals":    sorted(meals, key=lambda x: x.meal_time),
        }

    def weekly_summary(self) -> pd.DataFrame:
        meals = self.db.get_meals(7)
        if not meals:
            return pd.DataFrame()
        df = pd.DataFrame([{
            "date": m.meal_date, "calories": m.calories, "protein": m.protein
        } for m in meals])
        df["date"] = pd.to_datetime(df["date"])
        return (
            df.groupby(df["date"].dt.date)
              .agg(calories=("calories","sum"), protein=("protein","sum"))
              .reset_index()
        )

    def consistency_score(self) -> float:
        meals = self.db.get_meals(30)
        if not meals:
            return 0.0
        return round(len(set(m.meal_date for m in meals)) / 30 * 100, 1)

    def period_analysis(self) -> Dict[str, Any]:
        meals   = self.db.get_meals(30)
        periods = {"Manhã": 0, "Tarde": 0, "Noite": 0}
        counts  = {"Manhã": 0, "Tarde": 0, "Noite": 0}
        for m in meals:
            if not m.meal_time:
                continue
            try:
                h = int(m.meal_time.split(":")[0])
            except Exception:
                continue
            p = "Manhã" if h < 12 else "Tarde" if h < 18 else "Noite"
            periods[p] += m.calories
            counts[p]  += 1
        return {"calories_by_period": periods, "count_by_period": counts}

    def mood_analysis(self) -> Dict[str, int]:
        meals = self.db.get_meals(30)
        moods = {"great": 0, "good": 0, "neutral": 0, "bad": 0, "terrible": 0}
        for m in meals:
            if m.mood in moods:
                moods[m.mood] += 1
        return moods

    # ── ALERTAS CLÍNICOS ──────────────────────────────────────────────────────
    def calorie_alert(self, current: int, goal: int) -> Optional[str]:
        if goal <= 0:
            return None
        if 0 < current < config.MIN_CALORIES_SAFE:
            return (f"🚨 Consumo muito baixo ({current} kcal). "
                    "Déficits severos prejudicam o metabolismo e a massa muscular.")
        pct = current / goal
        if pct >= 1.0:
            return f"⚠️ Meta calórica atingida! {current} kcal consumidas."
        if pct >= config.ALERT_PCT_WARNING:
            return f"⚡ Restam {goal - current} kcal para a meta de hoje."
        return None

    def protein_alert(self, current: float, goal: float) -> Optional[str]:
        if goal <= 0 or current <= 0:
            return None
        if current / goal < 0.5:
            return (f"🥩 Proteína baixa: {current:.0f}g de {goal:.0f}g. "
                    "Fundamental para preservar massa muscular.")
        return None

    def glp1_low_calorie_alert(self) -> Optional[str]:
        """Alerta GLP-1: <900kcal por 3+ dias consecutivos."""
        consecutive = 0
        for i in range(config.GLP1_LOW_KCAL_DAYS):
            d   = (date.today() - timedelta(days=i)).isoformat()
            sm  = self.daily_summary(d)
            cal = sm.get("calories", 0)
            if 0 < cal < config.GLP1_LOW_KCAL_THRESHOLD:
                consecutive += 1
            else:
                break
        if consecutive >= config.GLP1_LOW_KCAL_DAYS:
            return (
                f"💉 Consumo abaixo de {config.GLP1_LOW_KCAL_THRESHOLD} kcal "
                f"por {consecutive} dias consecutivos. Com GLP-1 é essencial manter "
                f"ingestão adequada para preservar massa muscular. Consulte seu médico."
            )
        return None

    def bariatric_volume_alert(self, volume_ml: float, phase: str) -> Optional[str]:
        """Alerta se volume da refeição excede limite da fase bariátrica."""
        phase_data = config.BARIATRIC_PHASES.get(phase)
        if not phase_data or not volume_ml:
            return None
        max_ml = phase_data.get("max_ml", 999)
        if volume_ml > max_ml:
            return (
                f"🔪 Volume de {volume_ml:.0f}ml excede o limite da fase "
                f"{phase_data['name']} ({max_ml}ml). Fracione as refeições."
            )
        return None

    def protein_two_day_alert(self, prot_goal: float) -> Optional[str]:
        """Alerta se proteína <50% da meta por 2 dias consecutivos."""
        low_days = 0
        for i in range(2):
            d  = (date.today() - timedelta(days=i)).isoformat()
            sm = self.daily_summary(d)
            if sm["protein"] < prot_goal * 0.5:
                low_days += 1
        if low_days >= 2:
            return (
                f"🥩 Proteína abaixo de 50% da meta por 2 dias. "
                "Priorize fontes proteicas nas próximas refeições."
            )
        return None

    # ── SCORE NUTRICIONAL ─────────────────────────────────────────────────────
    def nutrient_score(self, food: dict) -> int:
        score = 50
        prot  = food.get("protein", 0)
        fiber = food.get("fiber", 0)
        cal   = food.get("calories", 0)
        fat   = food.get("fat", 0)
        if prot > 20:   score += 20
        elif prot > 10: score += 10
        if fiber > 5:   score += 15
        elif fiber > 2: score += 7
        if cal > 300 and prot < 5 and fiber < 1:
            score -= 20
        return max(0, min(100, score))

    # ── REGISTRO ──────────────────────────────────────────────────────────────
    def register_meal(self, food: dict, quantity: float,
                      meal_time: str, meal_type: str = "",
                      mood: str = "", volume_ml: float = 0.0) -> bool:
        try:
            score = self.nutrient_score(food)
            meal  = Meal(
                food=food["name"],
                calories=int(food["calories"] * quantity),
                protein=round(food.get("protein", 0) * quantity, 1),
                carbs=round(food.get("carbs", 0) * quantity, 1),
                fat=round(food.get("fat", 0) * quantity, 1),
                fiber=round(food.get("fiber", 0) * quantity, 1),
                quantity=quantity,
                volume_ml=volume_ml,
                meal_time=meal_time,
                meal_type=meal_type,
                mood=mood,
                nutrient_score=score,
            )
            return self.db.save_meal(meal)
        except Exception as e:
            logger.error(f"register_meal: {e}")
            return False

    # ── SUGESTÕES ─────────────────────────────────────────────────────────────
    def suggest_foods(self) -> List[str]:
        meals = self.db.get_meals(14)
        if not meals:
            return []
        from collections import Counter
        return [f for f, _ in Counter(m.food for m in meals).most_common(5)]
