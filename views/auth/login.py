"""Melshape — Tela de login (paciente e profissional)."""
import streamlit as st
from core.security import validate_email


def render(services: dict) -> None:
    db = services["db"]

    with st.form("login_form", clear_on_submit=False):
        st.markdown("#### 🔑 Entrar na sua conta")
        email    = st.text_input("Email", placeholder="seu@email.com")
        password = st.text_input("Senha", type="password")

        c1, c2 = st.columns(2)
        with c1:
            submit = st.form_submit_button("Entrar →", type="primary", use_container_width=True)
        with c2:
            pro_btn = st.form_submit_button("Sou Profissional", use_container_width=True)

        if submit:
            valid, msg = validate_email(email)
            if not valid:
                st.error(msg)
            elif not password:
                st.error("Informe a senha.")
            else:
                # Tenta como paciente
                user = db.get_user(email, password)
                if user:
                    st.session_state.user = user.to_dict()
                    st.session_state.page = (
                        "home" if user.onboarding_done else "onboarding"
                    )
                    st.rerun()
                else:
                    # Tenta como profissional
                    pro = db.get_professional(email, password)
                    if pro:
                        st.session_state.professional = pro.to_dict()
                        st.session_state.page = "pro_dashboard"
                        st.rerun()
                    else:
                        st.error("❌ Email ou senha incorretos.")

        if pro_btn:
            st.session_state.page = "register_pro"
            st.rerun()
