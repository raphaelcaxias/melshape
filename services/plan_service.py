"""Melshape — Serviço de planos e paywall."""
import streamlit as st
import config
from core.models import User


class PlanService:

    def __init__(self, db):
        self.db = db

    def _user(self, user: dict) -> User:
        return User.from_dict(user)

    def effective_plan(self, user: dict) -> str:
        return self._user(user).effective_plan()

    def can_use(self, user: dict, feature: str) -> bool:
        return self._user(user).can_use(feature)

    def meals_limit_today(self, user: dict) -> int:
        return self._user(user).meals_limit_today()

    def check_meal_limit(self, user: dict) -> tuple:
        limit   = self.meals_limit_today(user)
        current = self.db.count_meals_today()
        if current >= limit:
            plan = self.effective_plan(user)
            if plan == "free":
                return False, (
                    f"🔒 Limite de **{limit} refeições/dia** atingido no plano gratuito. "
                    f"Você registrou {current} de {limit}. Faça upgrade para continuar."
                )
        return True, ""

    def trial_banner(self, user: dict) -> None:
        u = self._user(user)
        if u.plan != "trial":
            return
        if not u.trial_expires_at:
            return
        days = u.trial_days_remaining()
        if days == 0:
            st.error("⏰ Seu trial expirou! Assine um plano para continuar.")
            return
        if days <= config.TRIAL_ALERT_DAYS:
            st.warning(
                f"⚡ Trial termina em **{days} dia(s)**! "
                "[Assine agora](javascript:void) para não perder o acesso."
            )

    def show_paywall(self, feature_name: str, user: dict) -> None:
        st.markdown("---")
        st.markdown(
            f'<div class="paywall-block">'
            f'<div style="font-size:2.5rem;">🔒</div>'
            f'<h3 style="font-family:Sora,sans-serif;color:#9a3412;margin:0.5rem 0;">'
            f'{feature_name} é exclusivo do plano Pro</h3>'
            f'<p style="color:#c2410c;margin:0;">Upgrade e desbloqueie todos os recursos.</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button("⭐ Ver Planos e Fazer Upgrade", use_container_width=True, type="primary"):
                st.session_state.page = "profile"
                st.rerun()
