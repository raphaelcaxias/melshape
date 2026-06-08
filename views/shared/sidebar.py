"""Melshape — Sidebar do paciente."""
import streamlit as st
import config

MENU = [
    ("🏠", "Início",      "home"),
    ("📊", "Dashboard",   "dashboard"),
    ("🍴", "Refeições",   "meals"),
    ("🏋️", "Treino",     "workout"),
    ("💊", "Suplementos", "supplements"),
    ("⚖️", "Peso",       "weight"),
    ("📈", "Análise",     "analysis"),
    ("👤", "Perfil",      "profile"),
]


def render(services: dict) -> None:
    u            = st.session_state.user
    nutrition    = services["nutrition"]
    gamification = services["gamification"]
    plan_svc     = services["plan"]
    db           = services["db"]

    with st.sidebar:
        # Logo
        st.markdown(
            '<div style="text-align:center;padding:1.1rem 0 0.9rem;border-bottom:1px solid #2a2a30;">'
            '<div style="font-size:2rem;">🔥</div>'
            '<div style="font-family:Sora,sans-serif;font-weight:800;font-size:1.2rem;color:#C9A84C;">Melshape</div>'
            '<div style="font-size:0.68rem;color:#666;margin-top:0.1rem;">Para quem está mudando de verdade.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Plano
        from core.models import User
        u_obj    = User.from_dict(u)
        eff_plan = u_obj.effective_plan()
        plan_labels = {
            "free":     "🆓 FREE",
            "trial":    f"⏳ TRIAL ({u_obj.trial_days_remaining()}d)",
            "essencial":"💎 ESSENCIAL",
            "pro":      "⭐ PRO",
            "lifetime": "👑 VITALÍCIO",
        }
        st.markdown(
            f'<div class="plan-{eff_plan}" style="margin:0.6rem 0;">'
            f'{plan_labels.get(eff_plan, "FREE")}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Trial banner
        plan_svc.trial_banner(u)

        # Modo de saúde
        mode_labels = {
            "general":   "⚖️ Emagrecimento",
            "bariatric": "🔪 Pós-Bariátrica",
            "glp1":      "💉 GLP-1",
            "fitness":   "💪 Fitness",
        }
        hm = u.get("health_mode", "general")
        st.markdown(
            f'<div class="mode-badge mode-{hm}" style="margin-bottom:0.45rem;">'
            f'{mode_labels.get(hm, "Geral")}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Usuário
        st.markdown(
            f'<div style="font-size:0.81rem;padding:0 0.2rem;margin-bottom:0.45rem;">'
            f'<b>👤 {u.get("name","")}</b><br>'
            f'<span style="color:#666;font-size:0.73rem;">📧 {u.get("email","")}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Resumo
        sm          = nutrition.daily_summary()
        sk          = gamification.streak()
        lvl         = gamification.level()
        hydration   = db.get_hydration_today()
        prot_goal   = nutrition.calc_protein_goal(
            float(u.get("current_weight") or 70), u.get("health_mode", "general")
        )

        st.markdown("---")
        st.metric("🔥 Calorias", f"{sm['calories']} kcal")
        st.metric("🥩 Proteínas", f"{sm['protein']:.0f}g / {prot_goal:.0f}g")
        st.metric("💧 Hidratação", f"{hydration} ml")
        st.metric("📅 Sequência",  f"{sk} dias")

        # Nível
        st.markdown(
            f'<div style="margin-top:0.45rem;">'
            f'<span class="level-badge">'
            f'{lvl["current"]["icon"]} Nível {lvl["current"]["level"]} · {lvl["current"]["name"]}'
            f'</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if lvl["next"]:
            pct = lvl["progress_pct"]
            st.markdown(
                f'<div style="background:#2a2a30;border-radius:9999px;height:4px;overflow:hidden;margin:0.45rem 0;">'
                f'<div style="background:linear-gradient(90deg,#C9A84C,#a8862e);height:100%;width:{pct}%;"></div>'
                f'</div>'
                f'<div style="font-size:0.68rem;color:#666;text-align:right;">{lvl["xp"]} XP</div>',
                unsafe_allow_html=True,
            )

        # Menu
        st.markdown("---")
        cur = st.session_state.page
        for icon, label, key in MENU:
            kind = "primary" if cur == key else "secondary"
            if st.button(f"{icon} {label}", use_container_width=True,
                         type=kind, key=f"nav_{key}"):
                st.session_state.page = key
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True):
            _clear_session()

        if u.get("email") == config.DEMO_EMAIL:
            st.markdown(
                '<div style="background:rgba(201,168,76,.12);border:1px solid rgba(201,168,76,.35);'
                'border-radius:7px;padding:0.35rem;text-align:center;font-size:0.72rem;color:#C9A84C;'
                'margin-top:0.4rem;">🎮 Modo Demo</div>',
                unsafe_allow_html=True,
            )


def _clear_session() -> None:
    import streamlit as st
    for key in ("user", "professional", "demo_loaded",
                "onboarding_step", "onboarding_mode", "pro_page", "pro_selected_patient"):
        st.session_state.pop(key, None)
    st.session_state.page = "landing"
    st.rerun()
