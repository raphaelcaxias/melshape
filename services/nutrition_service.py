"""
Melshape — Nutrition Service.

Serviço principal de nutrição: TMB, TDEE, metas, resumos diários/semanais,
validação cruzada de macros, alertas nutricionais e registro de refeições.

Princípios:
- Cálculos baseados em ciência (Harris-Benedict revisado)
- Metas personalizadas por modo de saúde (general/fitness/bariatric/glp1)
- Validação cruzada: alerta se macros não batem com calorias declaradas
- Alertas clínicos: déficit severo, proteína baixa, estagnação
- Integração com FoodService para sugestões de alimentos
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas

Views utilizadas:
    - vw_consumo_diario: sumário diário consolidado
    - vw_consumo_semanal: sumário semanal
    - vw_aderencia_nutricional: % de dias com registro

Arquitetura:
    NutritionService
    ├── Validação
    │   ├── cross_validate(calories, protein, carbs, fat) -> str | None
    │   └── validate_meal(food, quantity) -> str | None
    ├── Metabolismo
    │   ├── calc_tmb(weight, height, age, gender) -> int
    │   ├── calc_tdee(tmb, activity_level) -> int
    │   ├── calc_goal_calories(tmb, activity_level, goal, health_mode, workout_adjustment) -> int
    │   ├── calc_protein_goal(weight, health_mode) -> float
    │   ├── calc_macros_goal(goal_calories, goal) -> dict
    │   └── days_to_goal(current, goal_w) -> int | None
    ├── Resumos
    │   ├── daily_summary(date_str) -> dict
    │   ├── weekly_summary() -> pd.DataFrame
    │   ├── consistency_score() -> float
    │   └── period_analysis() -> dict
    ├── Alertas (delegados para nutrition_alerts.py)
    │   ├── calorie_alert(current, goal) -> str | None
    │   ├── protein_alert(current, goal) -> str | None
    │   ├── glp1_low_calorie_alert() -> str | None
    │   ├── bariatric_volume_alert(volume_ml, phase) -> str | None
    │   └── protein_two_day_alert(prot_goal) -> str | None
    ├── Registro
    │   └── register_meal(food, quantity, meal_time, meal_type, mood, volume_ml) -> tuple[bool, str | None]
    └── Sugestões
        └── suggest_foods() -> list[str]
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date, timedelta
from typing import Any

import pandas as pd

import config
from core.database import Database
from core.models import Meal
from services.nutrition_alerts import (
    bariatric_volume_alert,
    calorie_alert,
    glp1_low_calorie_alert,
    nutrient_score,
    protein_alert,
    protein_two_day_alert,
)

logger = logging.getLogger("Melshape.Nutrition")

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

_CROSS_THRESHOLD: float = 0.15  # 15% de tolerância na validação cruzada
_DEFAULT_TMB: int = 1500  # TMB padrão quando dados incompletos
_DEFAULT_PROTEIN: float = 120.0  # Proteína padrão quando peso não informado
_KG_FAT_IN_KCAL: int = 7700  # 1kg de gordura ≈ 7700kcal
_AVG_DAILY_DEFICIT: int = 500  # Déficit médio diário (kcal)


# ─────────────────────────────────────────────────────────────────────────────
# NUTRITION SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class NutritionService:
    """
    Serviço de nutrição: cálculos, resumos, alertas e registro.
    
    Example:
        >>> db = Database()
        >>> nutrition = NutritionService(db)
        >>> user = st.session_state.user
        >>> tmb = nutrition.calc_tmb(
        ...     weight=user.get("current_weight"),
        ...     height=user.get("height"),
        ...     age=user.get("age"),
        ...     gender=user.get("gender", "female")
        ... )
        >>> print(f"TMB: {tmb} kcal")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de nutrição.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ NutritionService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # VALIDAÇÃO CRUZADA
    # ─────────────────────────────────────────────────────────────────────────

    def cross_validate(
        self,
        calories: float,
        protein: float,
        carbs: float,
        fat: float,
    ) -> str | None:
        """
        Valida se as calorias declaradas batem com os macros calculados.
        
        Args:
            calories: Calorias declaradas (kcal)
            protein: Proteína (g)
            carbs: Carboidratos (g)
            fat: Gorduras (g)
            
        Returns:
            Mensagem de alerta se diferença > 15%, None caso contrário
            
        Example:
            >>> alerta = nutrition.cross_validate(500, 30, 50, 20)
            >>> if alerta:
            ...     print(alerta)
        """
        # Validações
        if calories <= 0:
            logger.debug("cross_validate: calorias <= 0, pulando validação")
            return None

        # Calcula calorias pelos macros (4kcal/g proteína, 4kcal/g carb, 9kcal/g gordura)
        calculated = (protein * 4) + (carbs * 4) + (fat * 9)

        if calculated == 0:
            logger.debug("cross_validate: macros calculados = 0, pulando validação")
            return None

        # Calcula diferença percentual
        diff_pct = abs(calories - calculated) / calories

        if diff_pct > _CROSS_THRESHOLD:
            alerta = (
                f"⚠️ Divergência nutricional: declarado {calories:.0f} kcal, "
                f"calculado pelos macros {calculated:.0f} kcal "
                f"({diff_pct * 100:.0f}% de diferença). "
                f"Verifique as quantidades registradas."
            )
            logger.warning(alerta)
            return alerta

        logger.debug(f"✅ Validação cruzada OK: {calories:.0f} kcal (diff: {diff_pct * 100:.1f}%)")
        return None

    def validate_meal(self, food: dict[str, Any], quantity: float) -> str | None:
        """
        Valida um alimento antes de registrar.
        
        Args:
            food: Dicionário com dados do alimento
            quantity: Quantidade (fator multiplicador)
            
        Returns:
            Mensagem de alerta ou None
            
        Example:
            >>> food = {"calories": 200, "protein": 30, "carbs": 20, "fat": 10}
            >>> alerta = nutrition.validate_meal(food, 1.5)
            >>> if alerta:
            ...     print(alerta)
        """
        # Validações
        if quantity <= 0:
            logger.warning(f"validate_meal: quantidade inválida: {quantity}")
            return None
        
        # Extrai dados do alimento
        data = self._extract_food_data(food, quantity)
        
        return self.cross_validate(
            calories=data["calories"],
            protein=data["protein"],
            carbs=data["carbs"],
            fat=data["fat"],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # METABOLISMO (TMB, TDEE, METAS)
    # ─────────────────────────────────────────────────────────────────────────

    def calc_tmb(
        self,
        weight: float | None,
        height: int | None,
        age: int | None,
        gender: str = "female",
    ) -> int:
        """
        Calcula a Taxa Metabólica Basal (TMB) usando Harris-Benedict revisado.
        
        Args:
            weight: Peso (kg)
            height: Altura (cm)
            age: Idade (anos)
            gender: Gênero (female/male)
            
        Returns:
            TMB em kcal/dia
            
        Example:
            >>> tmb = nutrition.calc_tmb(70, 170, 30, "female")
            >>> print(f"TMB: {tmb} kcal")
            
        Reference:
            - Mulher: 10 * peso + 6.25 * altura - 5 * idade - 161
            - Homem:  10 * peso + 6.25 * altura - 5 * idade + 5
    """
        # Validações
        if not all([weight, height, age]):
            logger.debug(f"Dados incompletos para TMB (weight={weight}, height={height}, age={age}), retornando {_DEFAULT_TMB}")
            return _DEFAULT_TMB
        
        if weight <= 0 or height <= 0 or age <= 0:
            logger.warning(f"Valores inválidos para TMB (weight={weight}, height={height}, age={age})")
            return _DEFAULT_TMB

        # Harris-Benedict revisado
        base = 10 * weight + 6.25 * height - 5 * age

        if gender == "male":
            tmb = int(base + 5)
        else:
            tmb = int(base - 161)

        logger.debug(f"TMB calculada: {tmb} kcal (gender={gender})")
        return tmb

    def calc_tdee(self, tmb: int, activity_level: str = "moderate") -> int:
        """
        Calcula o Gasto Energético Total Diário (TDEE).
        
        Args:
            tmb: Taxa Metabólica Basal (kcal)
            activity_level: Nível de atividade física
            
        Returns:
            TDEE em kcal/dia
            
        Example:
            >>> tdee = nutrition.calc_tdee(1400, "moderate")
            >>> print(f"TDEE: {tdee} kcal")
        """
        if tmb <= 0:
            logger.warning(f"TMB inválida: {tmb}")
            return 0
        
        factor = config.ACTIVITY_FACTORS.get(activity_level, 1.55)
        tdee = int(tmb * factor)
        
        logger.debug(f"TDEE calculado: {tdee} kcal (activity={activity_level}, factor={factor})")
        return tdee

    def calc_goal_calories(
        self,
        tmb: int,
        activity_level: str = "moderate",
        goal: str = "lose",
        health_mode: str = "general",
        workout_adjustment: int = 0,
    ) -> int:
        """
        Calcula a meta calórica diária baseada no objetivo e modo de saúde.
        
        Args:
            tmb: Taxa Metabólica Basal (kcal)
            activity_level: Nível de atividade física
            goal: Objetivo (lose/maintain/gain)
            health_mode: Modo de saúde (general/fitness/bariatric/glp1)
            workout_adjustment: Ajuste para treino (kcal)
            
        Returns:
            Meta calórica em kcal/dia
            
        Example:
            >>> goal_cal = nutrition.calc_goal_calories(1400, "moderate", "lose", "general")
            >>> print(f"Meta: {goal_cal} kcal")
        """
        tdee = self.calc_tdee(tmb, activity_level)
        
        if tdee == 0:
            logger.warning("TDEE = 0, retornando meta padrão")
            return 1500

        # Ajuste baseado no modo de saúde e objetivo
        if health_mode == "bariatric":
            base = max(config.MIN_CALORIES_SAFE, tdee - 300)
            logger.debug(f"Modo bariátrico: TDEE - 300 = {base} kcal")
        elif health_mode == "glp1":
            base = max(config.MIN_CALORIES_SAFE, tdee - 400)
            logger.debug(f"Modo GLP-1: TDEE - 400 = {base} kcal")
        elif goal == "lose":
            base = max(config.SAFE_MIN_CALORIES, tdee - 500)
            logger.debug(f"Objetivo perder: TDEE - 500 = {base} kcal")
        elif goal == "gain":
            base = tdee + 300
            logger.debug(f"Objetivo ganhar: TDEE + 300 = {base} kcal")
        else:  # maintain
            base = tdee
            logger.debug(f"Objetivo manter: TDEE = {base} kcal")

        goal_calories = base + workout_adjustment
        
        logger.info(f"✅ Meta calórica calculada: {goal_calories} kcal")
        return goal_calories

    def calc_protein_goal(
        self,
        weight: float | None,
        health_mode: str = "general",
    ) -> float:
        """
        Calcula a meta de proteína diária baseada no peso e modo de saúde.
        
        Args:
            weight: Peso (kg)
            health_mode: Modo de saúde (general/fitness/bariatric/glp1)
            
        Returns:
            Meta de proteína em g/dia
            
        Example:
            >>> protein_goal = nutrition.calc_protein_goal(70, "fitness")
            >>> print(f"Meta de proteína: {protein_goal}g")
        """
        if not weight or weight <= 0:
            logger.debug(f"Peso não informado ou inválido ({weight}), retornando {_DEFAULT_PROTEIN}g")
            return _DEFAULT_PROTEIN

        # Fatores por modo de saúde
        per_kg_map = {
            "glp1": config.GLP1_PROTEIN_PER_KG,
            "bariatric": config.BARIATRIC_PROTEIN_PER_KG,
            "fitness": config.FITNESS_PROTEIN_PER_KG,
            "general": config.GENERAL_PROTEIN_PER_KG,
        }
        
        per_kg = per_kg_map.get(health_mode, config.GENERAL_PROTEIN_PER_KG)
        protein_goal = round(weight * per_kg, 1)
        
        logger.debug(f"Meta de proteína calculada: {protein_goal}g (weight={weight}kg, per_kg={per_kg})")
        return protein_goal

    def calc_macros_goal(
        self,
        goal_calories: int,
        goal: str = "lose",
    ) -> dict[str, int]:
        """
        Calcula a distribuição de macronutrientes.
        
        Args:
            goal_calories: Meta calórica diária (kcal)
            goal: Objetivo (lose/maintain/gain)
            
        Returns:
            Dicionário com protein, carbs, fat (em gramas)
            
        Example:
            >>> macros = nutrition.calc_macros_goal(1800, "lose")
            >>> print(f"Proteína: {macros['protein']}g, Carbs: {macros['carbs']}g, Gordura: {macros['fat']}g")
        """
        if goal_calories <= 0:
            logger.warning(f"Meta calórica inválida: {goal_calories}")
            return {"protein": 0, "carbs": 0, "fat": 0}

        # Distribuições por objetivo
        if goal == "lose":
            # Alta proteína, moderado carb, moderado gordura
            protein_pct, carbs_pct, fat_pct = 0.30, 0.35, 0.35
        elif goal == "gain":
            # Moderado proteína, alto carb, baixo gordura
            protein_pct, carbs_pct, fat_pct = 0.25, 0.50, 0.25
        else:  # maintain
            # Balanceado
            protein_pct, carbs_pct, fat_pct = 0.25, 0.45, 0.30

        macros = {
            "protein": int(goal_calories * protein_pct / 4),  # 4kcal/g
            "carbs": int(goal_calories * carbs_pct / 4),      # 4kcal/g
            "fat": int(goal_calories * fat_pct / 9),          # 9kcal/g
        }
        
        logger.debug(f"Macros calculados: {macros} (goal={goal})")
        return macros

    def days_to_goal(
        self,
        current: float | None,
        goal_w: float | None,
    ) -> int | None:
        """
        Estima dias para atingir o peso objetivo.
        
        Args:
            current: Peso atual (kg)
            goal_w: Peso objetivo (kg)
            
        Returns:
            Número estimado de dias ou None
            
        Example:
            >>> days = nutrition.days_to_goal(75, 70)
            >>> print(f"Faltam aproximadamente {days} dias")
        """
        if not current or not goal_w or current <= 0 or goal_w <= 0:
            logger.debug(f"Pesos inválidos (current={current}, goal={goal_w})")
            return None
        
        if current == goal_w:
            logger.debug("Peso atual = peso objetivo")
            return 0

        # Calcula déficit necessário
        deficit_needed = self._calculate_deficit_needed(current, goal_w)
        days = int(deficit_needed / _AVG_DAILY_DEFICIT)
        
        logger.debug(f"Dias estimados para objetivo: {days} (deficit_needed={deficit_needed}kcal)")
        return days

    def _calculate_deficit_needed(self, current: float, goal_w: float) -> int:
        """
        Calcula o déficit calórico total necessário para atingir o objetivo.
        
        Args:
            current: Peso atual (kg)
            goal_w: Peso objetivo (kg)
            
        Returns:
            Déficit em kcal
        """
        weight_diff = abs(current - goal_w)
        return int(weight_diff * _KG_FAT_IN_KCAL)

    # ─────────────────────────────────────────────────────────────────────────
    # RESUMOS DIÁRIOS E SEMANAIS
    # ─────────────────────────────────────────────────────────────────────────

    def daily_summary(self, date_str: str | None = None) -> dict[str, Any]:
        """
        Retorna o resumo nutricional de um dia específico.
        
        Args:
            date_str: Data no formato YYYY-MM-DD (padrão: hoje)
            
        Returns:
            Dicionário com: calories, protein, carbs, fat, fiber, volume_ml, count, meals
            
        Example:
            >>> today = nutrition.daily_summary()
            >>> print(f"Calorias hoje: {today['calories']} kcal")
        """
        if not date_str:
            date_str = date.today().isoformat()

        # 1. Tenta Supabase via view consolidada
        if self.db.is_real and self.db.client:
            try:
                uid = self.db.uid()
                response = (
                    self.db.client.table("vw_consumo_diario")
                    .select("calorias, proteina, carboidratos, gorduras, fibras, total_refeicoes")
                    .eq("perfil_id", uid)
                    .eq("dia", date_str)
                    .limit(1)
                    .execute()
                )

                if response.data:
                    row = response.data[0]
                    summary = {
                        "calories": int(row.get("calorias") or 0),
                        "protein": float(row.get("proteina") or 0),
                        "carbs": float(row.get("carboidratos") or 0),
                        "fat": float(row.get("gorduras") or 0),
                        "fiber": float(row.get("fibras") or 0),
                        "volume_ml": 0.0,
                        "count": int(row.get("total_refeicoes") or 0),
                        "meals": [],
                    }
                    logger.debug(f"✅ Daily summary (Supabase view): {summary['calories']} kcal")
                    return summary
            except Exception as e:
                logger.warning(f"daily_summary view falhou: {e}")

        # 2. Fallback: soma local
        meals = self.db.get_meals_by_date(date_str)
        summary = {
            "calories": sum(m.calories for m in meals),
            "protein": round(sum(m.protein for m in meals), 1),
            "carbs": round(sum(m.carbs for m in meals), 1),
            "fat": round(sum(m.fat for m in meals), 1),
            "fiber": round(sum(m.fiber for m in meals), 1),
            "volume_ml": round(sum(m.volume_ml for m in meals), 0),
            "count": len(meals),
            "meals": sorted(meals, key=lambda x: x.meal_time),
        }
        
        logger.debug(f"✅ Daily summary (local): {summary['calories']} kcal, {summary['count']} refeições")
        return summary

    def weekly_summary(self) -> pd.DataFrame:
        """
        Retorna o resumo nutricional da última semana.
        
        Returns:
            DataFrame com colunas: date, calories, protein, carbs, fat
            
        Example:
            >>> df = nutrition.weekly_summary()
            >>> print(df.to_string())
        """
        # 1. Tenta Supabase via view
        if self.db.is_real and self.db.client:
            try:
                uid = self.db.uid()
                response = (
                    self.db.client.table("vw_consumo_semanal")
                    .select("ano, semana, calorias, proteina, carboidratos, gorduras")
                    .eq("perfil_id", uid)
                    .order("ano", desc=True)
                    .order("semana", desc=True)
                    .limit(8)
                    .execute()
                )

                if response.data:
                    df = pd.DataFrame(response.data)
                    logger.debug(f"✅ Weekly summary (Supabase view): {len(df)} semanas")
                    return df
            except Exception as e:
                logger.warning(f"weekly_summary view falhou: {e}")

        # 2. Fallback: calcula localmente
        meals = self.db.get_meals(7)
        if not meals:
            logger.debug("Weekly summary: nenhuma refeição encontrada")
            return pd.DataFrame()

        df = pd.DataFrame(
            [
                {
                    "date": m.meal_date,
                    "calories": m.calories,
                    "protein": m.protein,
                    "carbs": m.carbs,
                    "fat": m.fat,
                }
                for m in meals
            ]
        )
        df["date"] = pd.to_datetime(df["date"])
        result = (
            df.groupby(df["date"].dt.date)
            .agg(
                calories=("calories", "sum"),
                protein=("protein", "sum"),
                carbs=("carbs", "sum"),
                fat=("fat", "sum"),
            )
            .reset_index()
        )
        
        logger.debug(f"✅ Weekly summary (local): {len(result)} dias")
        return result

    def consistency_score(self) -> float:
        """
        Calcula o % de dias com registro nos últimos 30 dias.
        
        Returns:
            Percentual de consistência (0.0 a 100.0)
            
        Example:
            >>> score = nutrition.consistency_score()
            >>> print(f"Consistência: {score:.1f}%")
        """
        # 1. Tenta Supabase via view
        if self.db.is_real and self.db.client:
            try:
                uid = self.db.uid()
                response = (
                    self.db.client.table("vw_aderencia_nutricional")
                    .select("percentual_aderencia")
                    .eq("perfil_id", uid)
                    .limit(1)
                    .execute()
                )

                if response.data:
                    score = float(response.data[0].get("percentual_aderencia") or 0)
                    logger.debug(f"✅ Consistency score (Supabase view): {score:.1f}%")
                    return score
            except Exception as e:
                logger.warning(f"consistency_score view falhou: {e}")

        # 2. Fallback: calcula localmente
        meals = self.db.get_meals(30)
        if not meals:
            logger.debug("Consistency score: nenhuma refeição encontrada")
            return 0.0

        days_with_meals = len(set(m.meal_date for m in meals))
        score = round(days_with_meals / 30 * 100, 1)
        
        logger.debug(f"✅ Consistency score (local): {score:.1f}% ({days_with_meals}/30 dias)")
        return score

    def period_analysis(self) -> dict[str, Any]:
        """
        Analisa distribuição de refeições por período do dia.
        
        Returns:
            Dicionário com calories_by_period e count_by_period
            
        Example:
            >>> analysis = nutrition.period_analysis()
            >>> print(f"Calorias no almoço: {analysis['calories_by_period']['Tarde']}")
        """
        meals = self.db.get_meals(30)
        periods = {"Manhã": 0, "Tarde": 0, "Noite": 0}
        counts = {"Manhã": 0, "Tarde": 0, "Noite": 0}

        for meal in meals:
            if not meal.meal_time:
                continue

            try:
                hour = int(meal.meal_time.split(":")[0])
            except (ValueError, IndexError):
                continue

            if hour < 12:
                period = "Manhã"
            elif hour < 18:
                period = "Tarde"
            else:
                period = "Noite"

            periods[period] += meal.calories
            counts[period] += 1

        result = {
            "calories_by_period": periods,
            "count_by_period": counts,
        }
        
        logger.debug(f"✅ Period analysis: {counts}")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # ALERTAS NUTRICIONAIS
    # ─────────────────────────────────────────────────────────────────────────

    def calorie_alert(self, current: int, goal: int) -> str | None:
        """Delega para nutrition_alerts.calorie_alert."""
        return calorie_alert(current, goal)

    def protein_alert(self, current: float, goal: float) -> str | None:
        """Delega para nutrition_alerts.protein_alert."""
        return protein_alert(current, goal)

    def glp1_low_calorie_alert(self) -> str | None:
        """Delega para nutrition_alerts.glp1_low_calorie_alert."""
        return glp1_low_calorie_alert(self.daily_summary)

    def bariatric_volume_alert(self, volume_ml: float, phase: str) -> str | None:
        """Delega para nutrition_alerts.bariatric_volume_alert."""
        return bariatric_volume_alert(volume_ml, phase)

    def protein_two_day_alert(self, prot_goal: float) -> str | None:
        """Delega para nutrition_alerts.protein_two_day_alert."""
        return protein_two_day_alert(self.daily_summary, prot_goal)

    def nutrient_score(self, food: dict[str, Any]) -> int:
        """Delega para nutrition_alerts.nutrient_score."""
        return nutrient_score(food)

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTRO DE REFEIÇÕES
    # ─────────────────────────────────────────────────────────────────────────

    def register_meal(
        self,
        food: dict[str, Any],
        quantity: float,
        meal_time: str,
        meal_type: str = "",
        mood: str = "",
        volume_ml: float = 0.0,
    ) -> tuple[bool, str | None]:
        """
        Registra uma refeição com validação cruzada.
        
        Args:
            food: Dicionário com dados do alimento
            quantity: Quantidade (fator multiplicador)
            meal_time: Horário da refeição (HH:MM)
            meal_type: Tipo da refeição (cafe_manha/almoco/jantar/etc)
            mood: Humor no momento da refeição
            volume_ml: Volume (ml) - para bariátrica
            
        Returns:
            (sucesso: bool, alerta_divergência: str | None)
            
        Example:
            >>> food = {"name": "Frango Grelhado", "calories": 159, "protein": 32, "carbs": 0, "fat": 3.5}
            >>> ok, alerta = nutrition.register_meal(food, 1.5, "12:30", "almoco")
            >>> if ok:
            ...     print("Refeição registrada!")
            ...     if alerta:
            ...         print(alerta)
        """
        try:
            # Validações
            if quantity <= 0:
                logger.warning(f"register_meal: quantidade inválida: {quantity}")
                return False, None
            
            if not meal_time:
                logger.warning("register_meal: meal_time é obrigatório")
                return False, None
            
            # Extrai dados do alimento
            data = self._extract_food_data(food, quantity)
            
            # Validação cruzada
            alerta = self.cross_validate(
                calories=data["calories"],
                protein=data["protein"],
                carbs=data["carbs"],
                fat=data["fat"],
            )

            # Cria objeto Meal
            meal = Meal(
                food=data["name"],
                calories=int(data["calories"]),
                protein=round(data["protein"], 1),
                carbs=round(data["carbs"], 1),
                fat=round(data["fat"], 1),
                fiber=round(data["fiber"], 1),
                quantity=quantity,
                volume_ml=volume_ml,
                meal_time=meal_time,
                meal_type=meal_type,
                mood=mood,
                nutrient_score=self.nutrient_score(food),
            )

            # Salva no banco
            ok = self.db.save_meal(meal)

            if ok:
                logger.info(f"✅ Refeição registrada: {data['name']} - {meal.calories}kcal")
            else:
                logger.warning(f"❌ Falha ao registrar refeição: {data['name']}")

            return ok, alerta

        except Exception as e:
            logger.error(f"register_meal falhou: {e}", exc_info=True)
            return False, None

    def _extract_food_data(self, food: dict[str, Any], quantity: float) -> dict[str, Any]:
        """
        Extrai e normaliza dados do alimento, aplicando quantidade.
        
        Args:
            food: Dicionário com dados do alimento
            quantity: Quantidade (fator multiplicador)
            
        Returns:
            Dicionário com dados normalizados
        """
        # Suporta nomes em PT e EN
        name = food.get("name", food.get("nome", "Alimento"))
        cal = float(food.get("calories", food.get("calorias", 0))) * quantity
        prot = float(food.get("protein", food.get("proteina", 0))) * quantity
        carb = float(food.get("carbs", food.get("carboidratos", 0))) * quantity
        fat = float(food.get("fat", food.get("gorduras", 0))) * quantity
        fib = float(food.get("fiber", food.get("fibra", 0))) * quantity
        
        return {
            "name": name,
            "calories": cal,
            "protein": prot,
            "carbs": carb,
            "fat": fat,
            "fiber": fib,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # SUGESTÕES DE ALIMENTOS
    # ─────────────────────────────────────────────────────────────────────────

    def suggest_foods(self) -> list[str]:
        """
        Sugere alimentos com base no histórico do paciente.
        
        Returns:
            Lista com os 5 alimentos mais frequentes nos últimos 14 dias
            
        Example:
            >>> foods = nutrition.suggest_foods()
            >>> for f in foods:
            ...     print(f)
        """
        meals = self.db.get_meals(14)

        if not meals:
            logger.debug("suggest_foods: nenhuma refeição encontrada")
            return []

        food_counts = Counter(m.food for m in meals)
        suggestions = [food for food, _ in food_counts.most_common(5)]
        
        logger.debug(f"✅ Sugestões de alimentos: {suggestions}")
        return suggestions

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS AUXILIARES
    # ─────────────────────────────────────────────────────────────────────────

    def get_nutrition_profile(self, user: dict[str, Any]) -> dict[str, Any]:
        """
        Calcula perfil nutricional completo do usuário.
        
        Args:
            user: Dicionário com dados do usuário
            
        Returns:
            Dicionário com TMB, TDEE, metas e macros
            
        Example:
            >>> profile = nutrition.get_nutrition_profile(user)
            >>> print(f"TMB: {profile['tmb']} kcal")
            >>> print(f"TDEE: {profile['tdee']} kcal")
            >>> print(f"Meta: {profile['goal_calories']} kcal")
        """
        weight = user.get("current_weight")
        height = user.get("height")
        age = user.get("age")
        gender = user.get("gender", "female")
        activity_level = user.get("activity_level", "moderate")
        goal = user.get("goal", "lose")
        health_mode = user.get("health_mode", "general")
        
        tmb = self.calc_tmb(weight, height, age, gender)
        tdee = self.calc_tdee(tmb, activity_level)
        goal_calories = self.calc_goal_calories(tmb, activity_level, goal, health_mode)
        protein_goal = self.calc_protein_goal(weight, health_mode)
        macros = self.calc_macros_goal(goal_calories, goal)
        
        profile = {
            "tmb": tmb,
            "tdee": tdee,
            "goal_calories": goal_calories,
            "protein_goal": protein_goal,
            "macros": macros,
        }
        
        logger.debug(f"✅ Nutrition profile: TMB={tmb}, TDEE={tdee}, Goal={goal_calories}")
        return profile


__all__ = ["NutritionService"]
