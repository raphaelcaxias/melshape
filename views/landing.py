"""Melshape — Landing page."""
import streamlit as st
from views.components import feature_card
import config


def render(services: dict) -> None:
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)

    st.markdown(
        '<div class="hero-banner">'
        '<h1>🔥 Melshape</h1>'
        '<p>Para quem está mudando de verdade.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### ✨ Uma plataforma para cada jornada")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        feature_card("💉", "GLP-1 / Canetas",
                     "Ozempic, Mounjaro e outros. Preserve músculo, controle proteína e hidratação.")
    with c2:
        feature_card("🔪", "Pós-Bariátrica",
                     "Fases, porções em ml, suplementos essenciais. Do líquido à manutenção.")
    with c3:
        feature_card("🏋️", "Fitness",
                     "Protocolo por treino. Meta calórica que se adapta ao seu dia.")
    with c4:
        feature_card("⚖️", "Emagrecimento",
                     "Consistência, déficit inteligente e gamificação real.")

    st.markdown("---")
    col_cta, col_stats = st.columns([1, 1])

    with col_cta:
        st.markdown("### 🚀 10 dias grátis — sem cartão")
        st.markdown("Acesso completo ao plano Pro por 10 dias.")

        if st.button("🎮 Experimentar Demo Agora", use_container_width=True, type="primary"):
            _load_demo(services)

        st.markdown("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔑 Entrar", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()
        with c2:
            if st.button("📝 Criar Conta", use_container_width=True):
                st.session_state.page = "register"
                st.rerun()

        st.markdown("")
        if st.button("🏥 Sou Nutricionista / Médico", use_container_width=True):
            st.session_state.page = "register_pro"
            st.rerun()

    with col_stats:
        st.markdown("### 📊 Números reais")
        s1, s2 = st.columns(2)
        with s1:
            st.metric("Usuários Ativos", "10.000+")
            st.metric("Cirurgias/ano BR", "70.000+")
        with s2:
            st.metric("Usuários GLP-1 BR", "1M+")
            st.metric("Trial gratuito", "10 dias")

    if st.session_state.get("page") in ("login", "register", "register_pro"):
        st.markdown("---")
        from views.auth import login as login_view, register as register_view
        if st.session_state.page == "login":
            login_view.render(services)
        else:
            register_view.render(services)

    st.markdown('</div>', unsafe_allow_html=True)


def _load_demo(services: dict) -> None:
    from datetime import datetime, timedelta
    demo = {
        "email":            config.DEMO_EMAIL,
        "name":             config.DEMO_NAME,
        "password_hash":    "",
        "user_type":        "patient",
        "plan":             "pro",
        "trial_expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "gender":           "female",
        "age":              32,
        "height":           165,
        "current_weight":   82.0,
        "goal_weight":      70.0,
        "activity_level":   "moderate",
        "goal":             "lose",
        "health_mode":      "glp1",
        "uses_glp1":        True,
        "glp1_medication":  "Mounjaro (Tirzepatida)",
        "glp1_dose":        "5mg",
        "glp1_start_date":  "2025-01-01",
        "glp1_phase":       "maintenance",
        "protein_goal_per_kg": 1.6,
        "onboarding_done":  True,
        "dark_mode":        False,
    }
    if "mock_db" not in st.session_state:
        from core.database import _MOCK_DEFAULTS
        st.session_state.mock_db = {
            k: v.copy() if isinstance(v, (dict, list)) else v
            for k, v in _MOCK_DEFAULTS.items()
        }
    st.session_state.mock_db["users"][config.DEMO_EMAIL] = demo
    st.session_state.user         = demo
    st.session_state.page         = "home"
    st.session_state.demo_loaded  = False
    st.rerun()
