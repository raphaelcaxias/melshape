"""
Melshape — Camada de dados: Supabase com fallback MockDB.
"""
import logging
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta
from typing import Optional, List

from core.models import (
    User, Professional, Meal, WeightLog,
    Supplement, WorkoutLog, HydrationLog, SymptomLog, SleepLog, CycleLog,
)
from core.security import hash_password, verify_password

logger = logging.getLogger("Melshape.Database")

_MOCK_DEFAULTS = {
    "users": {}, "professionals": {},
    "meals": [], "weights": [], "supplements": [],
    "workouts": [], "achievements": [],
    "hydration": [], "symptoms": [], "sleep": [], "cycles": [],
}


class Database:
    """Abstração de banco: Supabase → MockDB automático."""

    def __init__(self):
        self.is_real = False
        self.client  = None
        try:
            if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
                from supabase import create_client
                self.client = create_client(
                    st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
                )
                self.is_real = True
                logger.info("✅ Supabase conectado")
        except Exception as e:
            logger.warning(f"⚠️ Modo offline: {e}")
        self._init_mock()

    # ── MOCK ──────────────────────────────────────────────────────────────────
    def _init_mock(self):
        if "mock_db" not in st.session_state:
            st.session_state.mock_db = {k: v.copy() if isinstance(v, (dict, list)) else v
                                         for k, v in _MOCK_DEFAULTS.items()}

    def _mock(self) -> dict:
        return st.session_state.mock_db

    # ── UID ───────────────────────────────────────────────────────────────────
    def uid(self) -> str:
        if self.is_real and self.client:
            try:
                u = self.client.auth.get_user()
                if u and u.user:
                    return u.user.id
            except Exception:
                pass
        u = st.session_state.get("user")
        if u:
            return u.get("email", "anon")
        return "anon"

    # ── HELPERS INTERNOS ──────────────────────────────────────────────────────
    def _filter_user(self, lst: list, uid: str) -> list:
        return [x for x in lst if x.get("user_id") == uid]

    def _filter_days(self, lst: list, days: Optional[int], date_field: str = "log_date") -> list:
        if not days:
            return lst
        cutoff = date.today() - timedelta(days=days)
        result = []
        for x in lst:
            try:
                d = datetime.strptime(x.get(date_field, "2000-01-01"), "%Y-%m-%d").date()
                if d >= cutoff:
                    result.append(x)
            except Exception:
                pass
        return result

    def _make_model(self, cls, row: dict):
        valid = {k: v for k, v in row.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

    # ═══════════════════════════════════════════════════════════════════════════
    # AUTH — USUÁRIOS
    # ═══════════════════════════════════════════════════════════════════════════
    def get_user(self, email: str, password: str) -> Optional[User]:
        if self.is_real and self.client:
            try:
                r = self.client.auth.sign_in_with_password({"email": email, "password": password})
                if r.user:
                    prof = self.client.table("profiles").select("*").eq("id", r.user.id).execute().data
                    p = prof[0] if prof else {}
                    return User.from_dict({**p, "email": email})
            except Exception as e:
                logger.error(f"Login Supabase: {e}")

        d = self._mock()["users"].get(email.lower())
        if d and verify_password(password, d.get("password_hash", "")):
            return User.from_dict(d)
        return None

    def create_user(self, email: str, password: str, name: str,
                    lgpd_ts: str = "", gender: str = "female") -> bool:
        from datetime import datetime
        import config
        if self.is_real and self.client:
            try:
                r = self.client.auth.sign_up({
                    "email": email, "password": password,
                    "options": {"data": {"name": name}},
                })
                if r.user:
                    return True
            except Exception as e:
                logger.error(f"Cadastro Supabase: {e}")

        users = self._mock()["users"]
        if email.lower() in users:
            return False
        trial_end = (datetime.utcnow() + timedelta(days=config.TRIAL_DAYS)).isoformat()
        users[email.lower()] = {
            "email": email.lower(), "name": name,
            "password_hash": hash_password(password),
            "user_type": "patient", "plan": "trial",
            "trial_started_at": datetime.utcnow().isoformat(),
            "trial_expires_at": trial_end,
            "lgpd_accepted_at": lgpd_ts, "gender": gender,
            "onboarding_done": False, "health_mode": "general",
        }
        return True

    def update_user(self, data: dict) -> bool:
        uid = self.uid()
        if self.is_real and self.client:
            try:
                self.client.table("profiles").update(data).eq("id", uid).execute()
                return True
            except Exception as e:
                logger.error(f"update_user: {e}")
        users = self._mock()["users"]
        if uid in users:
            users[uid].update(data)
            return True
        return False

    # AUTH — PROFISSIONAIS
    def get_professional(self, email: str, password: str) -> Optional[Professional]:
        d = self._mock()["professionals"].get(email.lower())
        if d and verify_password(password, d.get("password_hash", "")):
            return Professional.from_dict(d)
        return None

    def create_professional(self, email: str, password: str, name: str,
                             specialty: str, crn: str, lgpd_ts: str = "") -> bool:
        from datetime import datetime
        import config
        pros = self._mock()["professionals"]
        if email.lower() in pros:
            return False
        trial_end = (datetime.utcnow() + timedelta(days=config.TRIAL_DAYS)).isoformat()
        pros[email.lower()] = {
            "email": email.lower(), "name": name,
            "password_hash": hash_password(password),
            "user_type": "professional", "specialty": specialty,
            "crn_number": crn, "pro_plan": "starter", "patient_count": 0,
            "trial_expires_at": trial_end, "lgpd_accepted_at": lgpd_ts,
            "onboarding_done": False,
        }
        return True

    # ═══════════════════════════════════════════════════════════════════════════
    # REFEIÇÕES
    # ═══════════════════════════════════════════════════════════════════════════
    def save_meal(self, meal: Meal) -> bool:
        meal.user_id = self.uid()
        if self.is_real and self.client:
            try:
                self.client.table("meals").insert(meal.to_dict()).execute()
                return True
            except Exception as e:
                logger.error(f"save_meal: {e}")
        self._mock()["meals"].append(meal.to_dict())
        return True

    def get_meals(self, days: Optional[int] = 7) -> List[Meal]:
        uid = self.uid()
        if self.is_real and self.client:
            try:
                q = self.client.table("meals").select("*").eq("user_id", uid)
                if days:
                    cutoff = (date.today() - timedelta(days=days)).isoformat()
                    q = q.gte("meal_date", cutoff)
                rows = q.order("meal_date", desc=True).execute().data or []
                return [self._make_model(Meal, r) for r in rows]
            except Exception as e:
                logger.error(f"get_meals: {e}")
                return []
        data = self._filter_user(self._mock()["meals"], uid)
        data = self._filter_days(data, days, "meal_date")
        return [self._make_model(Meal, r) for r in data]

    def get_meals_by_date(self, date_str: str) -> List[Meal]:
        return [m for m in self.get_meals(None) if m.meal_date == date_str]

    def count_meals_today(self) -> int:
        return len(self.get_meals_by_date(date.today().isoformat()))

    def get_last_meals(self, limit: int = 10) -> List[Meal]:
        """Últimas refeições únicas por nome (para sugestão 'repetir')."""
        meals = self.get_meals(14)
        seen, result = set(), []
        for m in sorted(meals, key=lambda x: (x.meal_date, x.meal_time), reverse=True):
            if m.food not in seen:
                seen.add(m.food)
                result.append(m)
            if len(result) >= limit:
                break
        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # PESO
    # ═══════════════════════════════════════════════════════════════════════════
    def save_weight(self, w: WeightLog) -> bool:
        w.user_id = self.uid()
        if self.is_real and self.client:
            try:
                self.client.table("weight_logs").insert(w.to_dict()).execute()
                self.client.table("profiles").update(
                    {"current_weight": w.weight}
                ).eq("id", w.user_id).execute()
                return True
            except Exception as e:
                logger.error(f"save_weight: {e}")
        self._mock()["weights"].append(w.to_dict())
        uid = w.user_id
        if uid in self._mock()["users"]:
            self._mock()["users"][uid]["current_weight"] = w.weight
        return True

    def get_weights(self, days: int = 30) -> pd.DataFrame:
        uid = self.uid()
        if self.is_real and self.client:
            try:
                cutoff = (date.today() - timedelta(days=days)).isoformat()
                r = (self.client.table("weight_logs").select("*")
                     .eq("user_id", uid).gte("log_date", cutoff).execute())
                if r.data:
                    df = pd.DataFrame(r.data)
                    df["log_date"] = pd.to_datetime(df["log_date"])
                    return df.sort_values("log_date")
            except Exception as e:
                logger.error(f"get_weights: {e}")
        data = self._filter_user(self._mock()["weights"], uid)
        data = self._filter_days(data, days)
        if not data:
            return pd.DataFrame(columns=["log_date", "weight", "notes", "body_fat", "muscle_mass"])
        df = pd.DataFrame(data)
        df["log_date"] = pd.to_datetime(df["log_date"])
        return df.sort_values("log_date")

    # ═══════════════════════════════════════════════════════════════════════════
    # SUPLEMENTOS
    # ═══════════════════════════════════════════════════════════════════════════
    def save_supplement(self, s: Supplement) -> bool:
        s.user_id = self.uid()
        self._mock()["supplements"].append(s.to_dict())
        return True

    def get_supplements(self, days: int = 7) -> List[Supplement]:
        uid  = self.uid()
        data = self._filter_user(self._mock()["supplements"], uid)
        data = self._filter_days(data, days)
        return [self._make_model(Supplement, r) for r in data]

    def get_supplements_today(self) -> List[Supplement]:
        today = date.today().isoformat()
        return [s for s in self.get_supplements(1) if s.log_date == today]

    # ═══════════════════════════════════════════════════════════════════════════
    # TREINO
    # ═══════════════════════════════════════════════════════════════════════════
    def save_workout(self, w: WorkoutLog) -> bool:
        w.user_id = self.uid()
        self._mock()["workouts"].append(w.to_dict())
        return True

    def get_workout_today(self) -> Optional[WorkoutLog]:
        uid   = self.uid()
        today = date.today().isoformat()
        for w in reversed(self._mock()["workouts"]):
            if w.get("user_id") == uid and w.get("log_date") == today:
                return self._make_model(WorkoutLog, w)
        return None

    def get_workouts(self, days: int = 30) -> List[WorkoutLog]:
        uid  = self.uid()
        data = self._filter_user(self._mock()["workouts"], uid)
        data = self._filter_days(data, days)
        return [self._make_model(WorkoutLog, r) for r in data]

    # ═══════════════════════════════════════════════════════════════════════════
    # HIDRATAÇÃO
    # ═══════════════════════════════════════════════════════════════════════════
    def save_hydration(self, h: HydrationLog) -> bool:
        h.user_id = self.uid()
        self._mock()["hydration"].append(h.to_dict())
        return True

    def get_hydration_today(self) -> int:
        """Total ml bebidos hoje."""
        uid   = self.uid()
        today = date.today().isoformat()
        total = sum(
            x.get("amount_ml", 0)
            for x in self._mock()["hydration"]
            if x.get("user_id") == uid and x.get("log_date") == today
        )
        return total

    def get_hydration_logs_today(self) -> List[HydrationLog]:
        uid   = self.uid()
        today = date.today().isoformat()
        data  = [x for x in self._mock()["hydration"]
                 if x.get("user_id") == uid and x.get("log_date") == today]
        return [self._make_model(HydrationLog, r) for r in data]

    # ═══════════════════════════════════════════════════════════════════════════
    # SINTOMAS
    # ═══════════════════════════════════════════════════════════════════════════
    def save_symptom(self, s: SymptomLog) -> bool:
        s.user_id = self.uid()
        self._mock()["symptoms"].append(s.to_dict())
        return True

    def get_symptoms(self, days: int = 7) -> List[SymptomLog]:
        uid  = self.uid()
        data = self._filter_user(self._mock()["symptoms"], uid)
        data = self._filter_days(data, days)
        return [self._make_model(SymptomLog, r) for r in data]

    def consecutive_severe_symptom_days(self) -> int:
        """Dias consecutivos com sintomas severos (para alertas clínicos)."""
        logs = self.get_symptoms(14)
        if not logs:
            return 0
        dates_with_severe = sorted(set(
            s.log_date for s in logs if s.has_severe()
        ), reverse=True)
        if not dates_with_severe:
            return 0
        count = 1
        for i in range(1, len(dates_with_severe)):
            d1 = datetime.strptime(dates_with_severe[i-1], "%Y-%m-%d").date()
            d2 = datetime.strptime(dates_with_severe[i],   "%Y-%m-%d").date()
            if (d1 - d2).days == 1:
                count += 1
            else:
                break
        return count

    # ═══════════════════════════════════════════════════════════════════════════
    # SONO
    # ═══════════════════════════════════════════════════════════════════════════
    def save_sleep(self, s: SleepLog) -> bool:
        s.user_id = self.uid()
        self._mock()["sleep"].append(s.to_dict())
        return True

    def get_sleep_today(self) -> Optional[SleepLog]:
        uid   = self.uid()
        today = date.today().isoformat()
        for s in reversed(self._mock()["sleep"]):
            if s.get("user_id") == uid and s.get("log_date") == today:
                return self._make_model(SleepLog, s)
        return None

    def get_sleep_logs(self, days: int = 7) -> List[SleepLog]:
        uid  = self.uid()
        data = self._filter_user(self._mock()["sleep"], uid)
        data = self._filter_days(data, days)
        return [self._make_model(SleepLog, r) for r in data]

    # ═══════════════════════════════════════════════════════════════════════════
    # CICLO
    # ═══════════════════════════════════════════════════════════════════════════
    def save_cycle(self, c: CycleLog) -> bool:
        c.user_id = self.uid()
        self._mock()["cycles"].append(c.to_dict())
        return True

    def get_cycle_today(self) -> Optional[CycleLog]:
        uid   = self.uid()
        today = date.today().isoformat()
        for c in reversed(self._mock()["cycles"]):
            if c.get("user_id") == uid and c.get("log_date") == today:
                return self._make_model(CycleLog, c)
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # CONQUISTAS
    # ═══════════════════════════════════════════════════════════════════════════
    def unlock_achievement(self, name: str, title: str) -> bool:
        uid  = self.uid()
        achs = self._mock()["achievements"]
        if any(a.get("achievement_name") == name and a.get("user_id") == uid for a in achs):
            return False
        achs.append({
            "user_id": uid, "achievement_name": name,
            "title": title, "unlocked_at": date.today().isoformat(),
        })
        return True

    def get_achievements(self) -> List[dict]:
        uid = self.uid()
        return [a for a in self._mock()["achievements"] if a.get("user_id") == uid]

    # ═══════════════════════════════════════════════════════════════════════════
    # PAINEL PROFISSIONAL
    # ═══════════════════════════════════════════════════════════════════════════
    def get_patients_of_professional(self, professional_email: str) -> List[dict]:
        return [u for u in self._mock()["users"].values()
                if u.get("professional_id") == professional_email]

    def get_patient_summary(self, patient_email: str) -> dict:
        today  = date.today().isoformat()
        meals  = [m for m in self._mock()["meals"]  if m.get("user_id") == patient_email]
        weights= [w for w in self._mock()["weights"] if w.get("user_id") == patient_email]
        m_today= [m for m in meals if m.get("meal_date") == today]

        last_w  = weights[-1]["weight"]  if weights else None
        first_w = weights[0]["weight"]   if weights else None
        w_diff  = round(last_w - first_w, 1) if (last_w and first_w) else None

        # dias consecutivos sem registro
        all_dates = sorted(set(m.get("meal_date","") for m in meals), reverse=True)
        gap_days  = 0
        if all_dates:
            try:
                last_date = datetime.strptime(all_dates[0], "%Y-%m-%d").date()
                gap_days  = (date.today() - last_date).days
            except Exception:
                pass

        return {
            "cal_today":   sum(m.get("calories", 0) for m in m_today),
            "prot_today":  round(sum(m.get("protein", 0) for m in m_today), 1),
            "last_weight": last_w,
            "weight_diff": w_diff,
            "days_logged": len(set(m.get("meal_date") for m in meals)),
            "total_meals": len(meals),
            "gap_days":    gap_days,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # EXPORTAÇÃO
    # ═══════════════════════════════════════════════════════════════════════════
    def export_meals_csv(self) -> str:
        meals = self.get_meals(365)
        if not meals:
            return "data,horario,alimento,calorias,proteinas,carbos,gorduras,fibras,humor\n"
        header = "data,horario,alimento,calorias,proteinas,carbos,gorduras,fibras,humor"
        rows = [
            f"{m.meal_date},{m.meal_time},{m.food},{m.calories},"
            f"{m.protein},{m.carbs},{m.fat},{m.fiber},{m.mood}"
            for m in meals
        ]
        return header + "\n" + "\n".join(rows)

    def export_weights_csv(self) -> str:
        df = self.get_weights(365)
        if df.empty:
            return "data,peso,gordura_pct,massa_muscular_kg,notas\n"
        cols = [c for c in ["log_date","weight","body_fat","muscle_mass","notes"] if c in df.columns]
        return df[cols].to_csv(index=False)
