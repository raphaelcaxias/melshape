"""
Melshape — Database Records Mixin.

Gerencia registros do usuário: refeições, peso, hidratação, check-ins,
gamificação, suplementos, treinos, sintomas, sono e ciclo menstrual.

Princípios:
- Repository Pattern: cada entidade tem seus métodos
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Logging: operações são logadas
- Imutabilidade: modelos são frozen dataclasses (usa dataclasses.replace)
- Validação: dados são validados antes de salvar

Arquitetura:
    RecordsMixin
    ├── Refeições (save_meal, get_meals, get_last_meals)
    ├── Peso (save_weight, get_weights)
    ├── Hidratação (save_hydration, get_hydration_today)
    ├── Check-ins (save_checkin, get_checkin_today, get_checkin_streak)
    ├── Gamificação (get_xp, add_xp, unlock_achievement, get_achievements)
    ├── Suplementos (save_supplement, get_supplements)
    ├── Treinos (save_workout, get_workout_today)
    ├── Sintomas (save_symptom)
    ├── Sono (save_sleep)
    ├── Ciclo Menstrual (save_cycle)
    └── Exportação (export_meals_csv)
"""
from __future__ import annotations

import dataclasses
import logging
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from core.models import (
    CycleLog,
    HydrationLog,
    Meal,
    SleepLog,
    Supplement,
    SymptomLog,
    WeightLog,
    WorkoutLog,
)

logger = logging.getLogger("Melshape.Database.Records")


class RecordsMixin:
    """
    Mixin com métodos de CRUD para registros do usuário.
    
    Requer que a classe base tenha:
        - self.client (Supabase client)
        - self.is_real (bool)
        - self.uid() -> str
        - self.mock (dict)
        - self._filter_user() -> list
        - self._filter_days() -> list
        - self._make_model() -> Any
    
    Example:
        >>> class Database(RecordsMixin):
        ...     def __init__(self):
        ...         self.client = None
        ...         self.is_real = False
        ...         self.mock = {}
        ...     
        ...     def uid(self) -> str:
        ...         return "user@example.com"
        
        >>> db = Database()
        >>> meal = Meal(food="Frango", calories=200, protein=40, carbs=0, fat=5)
        >>> db.save_meal(meal)
        True
    """

    # ─────────────────────────────────────────────────────────────────────────
    # REFEIÇÕES
    # ─────────────────────────────────────────────────────────────────────────

    def save_meal(self, meal: Meal) -> bool:
        """
        Salva uma refeição.
        
        Args:
            meal: Objeto Meal a ser salvo
            
        Returns:
            True se salvo com sucesso, False caso contrário
            
        Example:
            >>> meal = Meal(
            ...     food="Peito de Frango",
            ...     calories=200,
            ...     protein=40,
            ...     carbs=0,
            ...     fat=5,
            ...     meal_type=MealType.ALMOCO
            ... )
            >>> db.save_meal(meal)
            True
        """
        # Cria cópia com user_id (imutabilidade)
        meal_with_uid = dataclasses.replace(meal, user_id=self.uid())
        
        if self.is_real and self.client:
            try:
                # Insere refeição
                ref_response = self.client.table("refeicoes").insert({
                    "perfil_id": meal_with_uid.user_id,
                    "tipo_refeicao": meal_with_uid.meal_type.value if hasattr(meal_with_uid.meal_type, "value") else meal_with_uid.meal_type,
                    "data_refeicao": meal_with_uid.meal_date.isoformat() if hasattr(meal_with_uid.meal_date, "isoformat") else meal_with_uid.meal_date,
                    "horario": meal_with_uid.meal_time or None,
                    "humor": meal_with_uid.mood or None,
                    "observacoes": meal_with_uid.notes or None,
                }).execute()
                
                if not ref_response.data:
                    logger.error("save_meal: Falha ao inserir refeição")
                    return False
                
                refeicao_id = ref_response.data[0]["id"]
                alimento_id = self._find_alimento_id(meal_with_uid.food)
                
                # Insere item da refeição
                self.client.table("itens_refeicao").insert({
                    "refeicao_id": refeicao_id,
                    "alimento_id": alimento_id,
                    "quantidade": meal_with_uid.quantity,
                    "calorias_calc": meal_with_uid.calories,
                    "proteina_calc": meal_with_uid.protein,
                    "carbo_calc": meal_with_uid.carbs,
                    "gordura_calc": meal_with_uid.fat,
                    "nome_livre": meal_with_uid.food if not alimento_id else None,
                }).execute()
                
                logger.debug(f"✅ Refeição salva no Supabase: {meal_with_uid.food}")
                return True
                
            except Exception as e:
                logger.error(f"save_meal Supabase: {e}")
        
        # Fallback MockDB
        self.mock["meals"].append(meal_with_uid.to_dict())
        logger.debug(f"✅ Refeição salva no MockDB: {meal_with_uid.food}")
        return True

    def get_meals(self, days: int | None = 7, limit: int = 100) -> list[Meal]:
        """
        Retorna refeições dos últimos N dias.
        
        Args:
            days: Número de dias (None = todos)
            limit: Limite de resultados
            
        Returns:
            Lista de objetos Meal
            
        Example:
            >>> meals = db.get_meals(days=7)
            >>> for meal in meals:
            ...     print(f"{meal.food}: {meal.calories} kcal")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                query = self.client.table("vw_refeicoes_nutricionais")
                query = query.select("*").eq("perfil_id", uid)
                
                if days:
                    cutoff = (date.today() - timedelta(days=days)).isoformat()
                    query = query.gte("criado_em", cutoff)
                
                response = query.order("criado_em", desc=True).limit(limit).execute()
                rows = response.data or []
                
                return [self._row_to_meal(row) for row in rows]
                
            except Exception as e:
                logger.error(f"get_meals Supabase: {e}")
                return []
        
        # Fallback MockDB
        data = self._filter_user(self.mock["meals"], uid)
        data = self._filter_days(data, days, "meal_date")
        
        return [self._make_model(Meal, row) for row in data]

    def get_meals_by_date(self, date_str: str) -> list[Meal]:
        """
        Retorna refeições de uma data específica.
        
        Args:
            date_str: Data no formato YYYY-MM-DD
            
        Returns:
            Lista de objetos Meal
            
        Example:
            >>> meals = db.get_meals_by_date("2026-06-23")
            >>> print(f"{len(meals)} refeições encontradas")
        """
        all_meals = self.get_meals(days=None)
        return [m for m in all_meals if m.meal_date == date_str]

    def get_last_meals(self, limit: int = 10) -> list[Meal]:
        """
        Retorna as últimas refeições (sem repetir alimentos).
        
        Args:
            limit: Número máximo de refeições
            
        Returns:
            Lista de objetos Meal únicos
            
        Example:
            >>> last_meals = db.get_last_meals(limit=5)
            >>> for meal in last_meals:
            ...     print(meal.food)
        """
        meals = self.get_meals(days=14, limit=limit * 2)
        seen = set()
        result = []
        
        # Ordena por data e horário (mais recente primeiro)
        sorted_meals = sorted(
            meals,
            key=lambda x: (x.meal_date, x.meal_time),
            reverse=True
        )
        
        for meal in sorted_meals:
            if meal.food not in seen:
                seen.add(meal.food)
                result.append(meal)
            
            if len(result) >= limit:
                break
        
        return result

    def _row_to_meal(self, row: dict[str, Any]) -> Meal:
        """
        Converte uma linha do banco para um objeto Meal.
        
        Args:
            row: Dicionário com dados do banco
            
        Returns:
            Instância de Meal
        """
        criado = row.get("criado_em", "")
        meal_date = criado[:10] if criado else date.today().isoformat()
        meal_time = criado[11:16] if len(criado) > 15 else ""
        
        return Meal(
            food=row.get("tipo_refeicao", "Refeição"),
            calories=int(row.get("calorias") or 0),
            protein=float(row.get("proteina") or 0),
            carbs=float(row.get("carboidratos") or 0),
            fat=float(row.get("gorduras") or 0),
            fiber=float(row.get("fibras") or 0),
            meal_date=meal_date,
            meal_time=meal_time,
            meal_type=row.get("tipo_refeicao", ""),
            user_id=row.get("perfil_id", ""),
        )

    def _find_alimento_id(self, nome: str) -> str | None:
        """
        Busca ID de um alimento pelo nome.
        
        Args:
            nome: Nome do alimento
            
        Returns:
            ID do alimento ou None se não encontrado
        """
        if not self.is_real or not self.client:
            return None
        
        try:
            response = (
                self.client.table("alimentos_base")
                .select("id")
                .eq("nome", nome)
                .limit(1)
                .execute()
            )
            return response.data[0]["id"] if response.data else None
        except Exception as e:
            logger.debug(f"_find_alimento_id: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # PESO
    # ─────────────────────────────────────────────────────────────────────────

    def save_weight(self, weight_log: WeightLog) -> bool:
        """
        Salva um registro de peso.
        
        Args:
            weight_log: Objeto WeightLog a ser salvo
            
        Returns:
            True se salvo com sucesso, False caso contrário
            
        Example:
            >>> weight = WeightLog(weight=75.5, log_date=date.today())
            >>> db.save_weight(weight)
            True
        """
        # Cria cópia com user_id (imutabilidade)
        weight_with_uid = dataclasses.replace(weight_log, user_id=self.uid())
        
        if self.is_real and self.client:
            try:
                # Insere pesagem
                self.client.table("pesagens").insert({
                    "perfil_id": weight_with_uid.user_id,
                    "peso": weight_with_uid.weight,
                    "data_pesagem": weight_with_uid.log_date.isoformat() if hasattr(weight_with_uid.log_date, "isoformat") else weight_with_uid.log_date,
                    "gordura_pct": weight_with_uid.body_fat or None,
                    "massa_muscular_kg": weight_with_uid.muscle_mass or None,
                    "observacoes": weight_with_uid.notes or None,
                    "origem": "manual",
                }).execute()
                
                # Atualiza peso atual no perfil
                self.client.table("perfis").update({
                    "peso_atual": weight_with_uid.weight
                }).eq("id", weight_with_uid.user_id).execute()
                
                logger.debug(f"✅ Peso salvo no Supabase: {weight_with_uid.weight}kg")
                return True
                
            except Exception as e:
                logger.error(f"save_weight Supabase: {e}")
        
        # Fallback MockDB
        self.mock["weights"].append(weight_with_uid.to_dict())
        
        # Atualiza peso atual do usuário
        uid = weight_with_uid.user_id
        if uid in self.mock["users"]:
            self.mock["users"][uid]["current_weight"] = weight_with_uid.weight
        
        logger.debug(f"✅ Peso salvo no MockDB: {weight_with_uid.weight}kg")
        return True

    def get_weights(self, days: int = 30) -> pd.DataFrame:
        """
        Retorna DataFrame com histórico de peso.
        
        Args:
            days: Número de dias de histórico
            
        Returns:
            DataFrame com colunas: log_date, weight, body_fat, muscle_mass, notes
            
        Example:
            >>> df = db.get_weights(days=30)
            >>> print(f"Média de peso: {df['weight'].mean():.1f}kg")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                cutoff = (date.today() - timedelta(days=days)).isoformat()
                
                response = (
                    self.client.table("pesagens")
                    .select("data_pesagem, peso, gordura_pct, massa_muscular_kg, observacoes")
                    .eq("perfil_id", uid)
                    .gte("data_pesagem", cutoff)
                    .order("data_pesagem")
                    .execute()
                )
                
                if response.data:
                    df = pd.DataFrame(response.data).rename(columns={
                        "data_pesagem": "log_date",
                        "peso": "weight",
                        "gordura_pct": "body_fat",
                        "massa_muscular_kg": "muscle_mass",
                        "observacoes": "notes",
                    })
                    df["log_date"] = pd.to_datetime(df["log_date"])
                    return df.sort_values("log_date")
                
            except Exception as e:
                logger.error(f"get_weights Supabase: {e}")
        
        # Fallback MockDB
        data = self._filter_user(self.mock["weights"], uid)
        data = self._filter_days(data, days)
        
        if not data:
            return pd.DataFrame(columns=["log_date", "weight", "notes", "body_fat", "muscle_mass"])
        
        df = pd.DataFrame(data)
        df["log_date"] = pd.to_datetime(df["log_date"])
        return df.sort_values("log_date")

    # ─────────────────────────────────────────────────────────────────────────
    # HIDRATAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def save_hydration(self, hydration_log: HydrationLog) -> bool:
        """
        Salva um registro de hidratação.
        
        Args:
            hydration_log: Objeto HydrationLog a ser salvo
            
        Returns:
            True se salvo com sucesso, False caso contrário
            
        Example:
            >>> hydration = HydrationLog(amount_ml=500, source=HydrationSource.WATER)
            >>> db.save_hydration(hydration)
            True
        """
        # Cria cópia com user_id (imutabilidade)
        hydration_with_uid = dataclasses.replace(hydration_log, user_id=self.uid())
        
        if self.is_real and self.client:
            try:
                self.client.table("registros_agua").insert({
                    "perfil_id": hydration_with_uid.user_id,
                    "quantidade_ml": hydration_with_uid.amount_ml,
                    "data_registro": hydration_with_uid.log_date.isoformat() if hasattr(hydration_with_uid.log_date, "isoformat") else hydration_with_uid.log_date,
                    "horario": hydration_with_uid.log_time or None,
                    "fonte": hydration_with_uid.source.value if hasattr(hydration_with_uid.source, "value") else hydration_with_uid.source,
                }).execute()
                
                logger.debug(f"✅ Hidratação salva no Supabase: {hydration_with_uid.amount_ml}ml")
                return True
                
            except Exception as e:
                logger.error(f"save_hydration Supabase: {e}")
        
        # Fallback MockDB
        self.mock["hydration"].append(hydration_with_uid.to_dict())
        logger.debug(f"✅ Hidratação salva no MockDB: {hydration_with_uid.amount_ml}ml")
        return True

    def get_hydration_today(self) -> int:
        """
        Retorna total de ml de água hoje.
        
        Returns:
            Total em mililitros
            
        Example:
            >>> total_ml = db.get_hydration_today()
            >>> print(f"Hidratação hoje: {total_ml}ml")
        """
        uid = self.uid()
        today = date.today().isoformat()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("registros_agua")
                    .select("quantidade_ml")
                    .eq("perfil_id", uid)
                    .eq("data_registro", today)
                    .execute()
                )
                return sum(x.get("quantidade_ml", 0) for x in (response.data or []))
                
            except Exception as e:
                logger.error(f"get_hydration_today Supabase: {e}")
        
        # Fallback MockDB
        return sum(
            x.get("amount_ml", 0)
            for x in self.mock["hydration"]
            if x.get("user_id") == uid and x.get("log_date") == today
        )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK-IN
    # ─────────────────────────────────────────────────────────────────────────

    def save_checkin(
        self,
        humor: int,
        energia: int,
        sono: float,
        notes: str = "",
    ) -> bool:
        """
        Salva um check-in diário.
        
        Args:
            humor: Nível de humor (1-5)
            energia: Nível de energia (1-5)
            sono: Horas de sono
            notes: Observações opcionais
            
        Returns:
            True se salvo com sucesso, False caso contrário
            
        Example:
            >>> db.save_checkin(humor=4, energia=5, sono=7.5, notes="Ótimo dia!")
            True
        """
        uid = self.uid()
        today = date.today().isoformat()
        
        # Validação
        if not (1 <= humor <= 5):
            logger.warning(f"save_checkin: humor inválido: {humor}")
            return False
        
        if not (1 <= energia <= 5):
            logger.warning(f"save_checkin: energia inválida: {energia}")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.table("checkins").upsert({
                    "perfil_id": uid,
                    "data_checkin": today,
                    "humor": humor,
                    "energia": energia,
                    "qualidade_sono": sono,
                    "observacoes": notes or None,
                }, on_conflict="perfil_id,data_checkin").execute()
                
                logger.debug(f"✅ Check-in salvo no Supabase: {today}")
                return True
                
            except Exception as e:
                logger.error(f"save_checkin Supabase: {e}")
        
        # Fallback MockDB
        self.mock["checkins"].append({
            "user_id": uid,
            "log_date": today,
            "humor": humor,
            "energia": energia,
            "qualidade_sono": sono,
            "notes": notes,
        })
        
        logger.debug(f"✅ Check-in salvo no MockDB: {today}")
        return True

    def get_checkin_today(self) -> dict[str, Any] | None:
        """
        Retorna o check-in de hoje ou None.
        
        Returns:
            Dicionário com dados do check-in ou None
            
        Example:
            >>> checkin = db.get_checkin_today()
            >>> if checkin:
            ...     print(f"Humor: {checkin['humor']}")
        """
        uid = self.uid()
        today = date.today().isoformat()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("checkins")
                    .select("*")
                    .eq("perfil_id", uid)
                    .eq("data_checkin", today)
                    .limit(1)
                    .execute()
                )
                return response.data[0] if response.data else None
                
            except Exception as e:
                logger.error(f"get_checkin_today Supabase: {e}")
        
        # Fallback MockDB
        for checkin in reversed(self.mock["checkins"]):
            if checkin.get("user_id") == uid and checkin.get("log_date") == today:
                return checkin
        
        return None

    def get_checkin_streak(self) -> int:
        """
        Calcula a sequência atual de check-ins.
        
        Returns:
            Número de dias consecutivos com check-in
            
        Example:
            >>> streak = db.get_checkin_streak()
            >>> print(f"Sequência: {streak} dias")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("checkins")
                    .select("data_checkin")
                    .eq("perfil_id", uid)
                    .order("data_checkin", desc=True)
                    .limit(60)
                    .execute()
                )
                dates = [x["data_checkin"] for x in (response.data or [])]
            except Exception as e:
                logger.error(f"get_checkin_streak Supabase: {e}")
                dates = []
        else:
            # MockDB
            dates = sorted(
                set(
                    c.get("log_date", "")
                    for c in self.mock["checkins"]
                    if c.get("user_id") == uid
                ),
                reverse=True,
            )
        
        # Calcula streak
        streak = 0
        check_date = date.today()
        
        for date_str in dates:
            try:
                checkin_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue
            
            if checkin_date == check_date:
                streak += 1
                check_date -= timedelta(days=1)
            elif checkin_date < check_date:
                break
        
        return streak

    # ─────────────────────────────────────────────────────────────────────────
    # GAMIFICAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def get_xp(self) -> int:
        """
        Retorna XP total do usuário.
        
        Returns:
            Total de XP
            
        Example:
            >>> xp = db.get_xp()
            >>> print(f"XP total: {xp}")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("experiencia_usuario")
                    .select("xp_total")
                    .eq("perfil_id", uid)
                    .limit(1)
                    .execute()
                )
                return response.data[0]["xp_total"] if response.data else 0
                
            except Exception as e:
                logger.error(f"get_xp Supabase: {e}")
        
        return 0

    def add_xp(self, amount: int, motivo: str = "") -> bool:
        """
        Adiciona XP ao usuário via RPC.
        
        Args:
            amount: Quantidade de XP a adicionar
            motivo: Motivo da adição (opcional)
            
        Returns:
            True se adicionado com sucesso, False caso contrário
            
        Example:
            >>> db.add_xp(50, motivo="Check-in diário")
            True
        """
        uid = self.uid()
        
        if amount <= 0:
            logger.warning(f"add_xp: amount inválido: {amount}")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.rpc("fn_ganhar_xp", {
                    "p_perfil_id": uid,
                    "p_xp": amount,
                    "p_motivo": motivo,
                }).execute()
                
                logger.debug(f"✅ XP adicionado: +{amount} ({motivo})")
                return True
                
            except Exception as e:
                logger.error(f"add_xp Supabase: {e}")
        
        return False

    def unlock_achievement(self, name: str, title: str) -> bool:
        """
        Desbloqueia uma conquista para o usuário.
        
        Args:
            name: Nome interno da conquista
            title: Título exibido ao usuário
            
        Returns:
            True se desbloqueada, False se já existia
            
        Example:
            >>> db.unlock_achievement("first_checkin", "Primeiro Check-in")
            True
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                # Busca badge
                badge_response = (
                    self.client.table("badges")
                    .select("id")
                    .eq("nome", title)
                    .limit(1)
                    .execute()
                )
                
                if not badge_response.data:
                    logger.warning(f"unlock_achievement: Badge não encontrado: {title}")
                    return False
                
                badge_id = badge_response.data[0]["id"]
                
                # Verifica se já existe
                exists_response = (
                    self.client.table("badges_usuario")
                    .select("id")
                    .eq("perfil_id", uid)
                    .eq("badge_id", badge_id)
                    .limit(1)
                    .execute()
                )
                
                if exists_response.data:
                    logger.debug(f"unlock_achievement: Já desbloqueada: {title}")
                    return False
                
                # Desbloqueia
                self.client.table("badges_usuario").insert({
                    "perfil_id": uid,
                    "badge_id": badge_id,
                }).execute()
                
                logger.info(f"✅ Conquista desbloqueada: {title}")
                return True
                
            except Exception as e:
                logger.error(f"unlock_achievement Supabase: {e}")
        
        # Fallback MockDB
        achievements = self.mock["achievements"]
        
        # Verifica se já existe
        if any(
            a.get("achievement_name") == name and a.get("user_id") == uid
            for a in achievements
        ):
            logger.debug(f"unlock_achievement: Já desbloqueada: {name}")
            return False
        
        # Desbloqueia
        achievements.append({
            "user_id": uid,
            "achievement_name": name,
            "title": title,
            "unlocked_at": date.today().isoformat(),
        })
        
        logger.info(f"✅ Conquista desbloqueada (MockDB): {title}")
        return True

    def get_achievements(self) -> list[dict[str, Any]]:
        """
        Retorna conquistas desbloqueadas pelo usuário.
        
        Returns:
            Lista de dicionários com conquistas
            
        Example:
            >>> achievements = db.get_achievements()
            >>> for ach in achievements:
            ...     print(f"{ach['title']} - {ach['unlocked_at']}")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("vw_conquistas_usuario")
                    .select("badge, categoria, conquistado_em")
                    .eq("perfil_id", uid)
                    .execute()
                )
                
                return [
                    {
                        "achievement_name": x.get("badge", ""),
                        "title": x.get("badge", ""),
                        "unlocked_at": x.get("conquistado_em", ""),
                    }
                    for x in (response.data or [])
                ]
                
            except Exception as e:
                logger.error(f"get_achievements Supabase: {e}")
        
        # Fallback MockDB
        return [
            a for a in self.mock["achievements"]
            if a.get("user_id") == uid
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # SUPLEMENTOS
    # ─────────────────────────────────────────────────────────────────────────

    def save_supplement(self, supplement: Supplement) -> bool:
        """
        Salva um suplemento.
        
        Args:
            supplement: Objeto Supplement a ser salvo
            
        Returns:
            True se salvo com sucesso, False caso contrário
            
        Example:
            >>> supp = Supplement(name="Whey Protein", dose="30", unit="g")
            >>> db.save_supplement(supp)
            True
        """
        # Cria cópia com user_id (imutabilidade)
        supp_with_uid = dataclasses.replace(supplement, user_id=self.uid())
        
        # TODO: Implementar Supabase quando tabela estiver pronta
        # if self.is_real and self.client:
        #     try:
        #         self.client.table("suplementos").insert({...}).execute()
        #         return True
        #     except Exception as e:
        #         logger.error(f"save_supplement Supabase: {e}")
        
        # Fallback MockDB
        self.mock["supplements"].append(supp_with_uid.to_dict())
        logger.debug(f"✅ Suplemento salvo: {supp_with_uid.name}")
        return True

    def get_supplements(self, days: int = 7) -> list[Supplement]:
        """
        Retorna suplementos dos últimos N dias.
        
        Args:
            days: Número de dias
            
        Returns:
            Lista de objetos Supplement
            
        Example:
            >>> supps = db.get_supplements(days=7)
            >>> for supp in supps:
            ...     print(f"{supp.name}: {supp.dose}{supp.unit}")
        """
        uid = self.uid()
        data = self._filter_user(self.mock["supplements"], uid)
        data = self._filter_days(data, days)
        
        return [self._make_model(Supplement, row) for row in data]

    # ─────────────────────────────────────────────────────────────────────────
    # TREINOS
    # ─────────────────────────────────────────────────────────────────────────

    def save_workout(self, workout: WorkoutLog) -> bool:
        """
        Salva um treino.
        
        Args:
            workout: Objeto WorkoutLog a ser salvo
            
        Returns:
            True se salvo com sucesso, False caso contrário
            
        Example:
            >>> workout = WorkoutLog(workout_type=WorkoutType.STRENGTH, duration=60)
            >>> db.save_workout(workout)
            True
        """
        # Cria cópia com user_id (imutabilidade)
        workout_with_uid = dataclasses.replace(workout, user_id=self.uid())
        
        # TODO: Implementar Supabase quando tabela estiver pronta
        # if self.is_real and self.client:
        #     try:
        #         self.client.table("treinos").insert({...}).execute()
        #         return True
        #     except Exception as e:
        #         logger.error(f"save_workout Supabase: {e}")
        
        # Fallback MockDB
        self.mock["workouts"].append(workout_with_uid.to_dict())
        logger.debug(f"✅ Treino salvo: {workout_with_uid.workout_type}")
        return True

    def get_workout_today(self) -> WorkoutLog | None:
        """
        Retorna o treino de hoje.
        
        Returns:
            Objeto WorkoutLog ou None
            
        Example:
            >>> workout = db.get_workout_today()
            >>> if workout:
            ...     print(f"Treino: {workout.workout_type} - {workout.duration}min")
        """
        uid = self.uid()
        today = date.today().isoformat()
        
        for workout_data in reversed(self.mock["workouts"]):
            if workout_data.get("user_id") == uid and workout_data.get("log_date") == today:
                return self._make_model(WorkoutLog, workout_data)
        
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # SINTOMAS
    # ─────────────────────────────────────────────────────────────────────────

    def save_symptom(self, symptom: SymptomLog) -> bool:
        """
        Salva um sintoma.
        
        Args:
            symptom: Objeto SymptomLog a ser salvo
            
        Returns:
            True se salvo com sucesso, False caso contrário
            
        Example:
            >>> symptom = SymptomLog(symptom="nausea", severity=2)
            >>> db.save_symptom(symptom)
            True
        """
        # Cria cópia com user_id (imutabilidade)
        symptom_with_uid = dataclasses.replace(symptom, user_id=self.uid())
        
        # TODO: Implementar Supabase quando tabela estiver pronta
        # if self.is_real and self.client:
        #     try:
        #         self.client.table("sintomas").insert({...}).execute()
        #         return True
        #     except Exception as e:
        #         logger.error(f"save_symptom Supabase: {e}")
        
        # Fallback MockDB
        self.mock["symptoms"].append(symptom_with_uid.to_dict())
        logger.debug(f"✅ Sintoma salvo: {symptom_with_uid.symptom}")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # SONO
    # ─────────────────────────────────────────────────────────────────────────

    def save_sleep(self, sleep_log: SleepLog) -> bool:
        """
        Salva um registro de sono.
        
        Args:
            sleep_log: Objeto SleepLog a ser salvo
            
        Returns:
            True se salvo com sucesso, False caso contrário
            
        Example:
            >>> sleep = SleepLog(hours=7.5, quality=4)
            >>> db.save_sleep(sleep)
            True
        """
        # Cria cópia com user_id (imutabilidade)
        sleep_with_uid = dataclasses.replace(sleep_log, user_id=self.uid())
        
        # TODO: Implementar Supabase quando tabela estiver pronta
        # if self.is_real and self.client:
        #     try:
        #         self.client.table("sono").insert({...}).execute()
        #         return True
        #     except Exception as e:
        #         logger.error(f"save_sleep Supabase: {e}")
        
        # Fallback MockDB
        self.mock["sleep"].append(sleep_with_uid.to_dict())
        logger.debug(f"✅ Sono salvo: {sleep_with_uid.hours}h")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # CICLO MENSTRUAL
    # ─────────────────────────────────────────────────────────────────────────

    def save_cycle(self, cycle_log: CycleLog) -> bool:
        """
        Salva um registro de ciclo menstrual.
        
        Args:
            cycle_log: Objeto CycleLog a ser salvo
            
        Returns:
            True se salvo com sucesso, False caso contrário
            
        Example:
            >>> cycle = CycleLog(phase=CyclePhase.MENSTRUAL, flow=CycleFlow.MODERATE)
            >>> db.save_cycle(cycle)
            True
        """
        # Cria cópia com user_id (imutabilidade)
        cycle_with_uid = dataclasses.replace(cycle_log, user_id=self.uid())
        
        # TODO: Implementar Supabase quando tabela estiver pronta
        # if self.is_real and self.client:
        #     try:
        #         self.client.table("ciclos").insert({...}).execute()
        #         return True
        #     except Exception as e:
        #         logger.error(f"save_cycle Supabase: {e}")
        
        # Fallback MockDB
        self.mock["cycles"].append(cycle_with_uid.to_dict())
        logger.debug(f"✅ Ciclo salvo: {cycle_with_uid.phase}")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # EXPORTAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def export_meals_csv(self) -> str:
        """
        Exporta refeições como CSV.
        
        Returns:
            String CSV com todas as refeições do último ano
            
        Example:
            >>> csv_data = db.export_meals_csv()
            >>> with open("refeicoes.csv", "w") as f:
            ...     f.write(csv_data)
        """
        meals = self.get_meals(days=365)
        
        if not meals:
            return "data,horario,alimento,calorias,proteinas,carbos,gorduras,fibras,humor\n"
        
        # Usa pandas para gerar CSV (mais robusto)
        data = [
            {
                "data": m.meal_date,
                "horario": m.meal_time,
                "alimento": m.food,
                "calorias": m.calories,
                "proteinas": m.protein,
                "carbos": m.carbs,
                "gorduras": m.fat,
                "fibras": m.fiber,
                "humor": m.mood,
            }
            for m in meals
        ]
        
        df = pd.DataFrame(data)
        return df.to_csv(index=False)


__all__ = ["RecordsMixin"]
