"""Melshape — Cadastro de paciente e profissional com email de boas-vindas."""
import streamlit as st
from core.security import lgpd_consent_text, record_lgpd_consent
from utils.validators import validate_registration
from services.email_service import send_welcome
import config


def render(services: dict) -> None:
    db     = services["db"]
    is_pro = st.session_state.get("page") == "register_pro"
    label  = "🏥 Profissional de Saúde" if is_pro else "👤 Paciente"
    st.markdown(f"#### 📝 Criar conta — {label}")
    if is_pro:
        _pro_form(db)
    else:
        _patient_form(db)


def _patient_form(db) -> None:
    with st.form("register_patient", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            name     = st.text_input("Nome completo")
            email    = st.text_input("Email", placeholder="seu@email.com")
            gender   = st.selectbox(
                "Gênero", ["female", "male", "other"],
                format_func=lambda x: {"female":"Feminino","male":"Masculino","other":"Outro"}[x],
            )
        with c2:
            password  = st.text_input("Senha (mín. 6 caracteres)", type="password")
            password2 = st.text_input("Confirmar senha", type="password")

        st.markdown(lgpd_consent_text())
        lgpd = st.checkbox("Li e aceito os Termos de Uso e Política de Privacidade")

        if st.form_submit_button("Criar Conta →", type="primary", use_container_width=True):
            if password != password2:
                st.error("As senhas não coincidem.")
                return
            errors = validate_registration(name, email, password, lgpd)
            if errors:
                for e in errors:
                    st.error(e)
                return

            lgpd_ts = record_lgpd_consent(email)
            if db.create_user(email, password, name, lgpd_ts=lgpd_ts, gender=gender):
                user = db.get_user(email, password)
                if user:
                    st.session_state.user = user.to_dict()
                    st.session_state.page = "onboarding"
                    # Envia email de boas-vindas em background (não bloqueia a UI)
                    try:
                        send_welcome(email, name, config.TRIAL_DAYS)
                    except Exception:
                        pass  # Email falhou mas cadastro ok
                    st.success("✅ Conta criada! Trial de 10 dias iniciado.")
                    st.rerun()
            else:
                st.error("❌ Email já cadastrado. Tente fazer login.")


def _pro_form(db) -> None:
    with st.form("register_pro", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            name      = st.text_input("Nome completo")
            email     = st.text_input("Email profissional")
            specialty = st.selectbox(
                "Especialidade",
                ["nutritionist","endocrinologist","other"],
                format_func=lambda x: {
                    "nutritionist":    "🥗 Nutricionista",
                    "endocrinologist": "🩺 Endocrinologista",
                    "other":           "👨‍⚕️ Outro Profissional",
                }[x],
            )
        with c2:
            password = st.text_input("Senha", type="password")
            crn      = st.text_input("CRN / CRM / Registro profissional")

        st.markdown(lgpd_consent_text())
        lgpd = st.checkbox("Li e aceito os Termos de Uso e Política de Privacidade")

        if st.form_submit_button("Criar Conta Profissional →", type="primary", use_container_width=True):
            if not lgpd:
                st.error("Aceite os termos para continuar.")
                return
            if not all([name, email, password, crn]):
                st.error("Preencha todos os campos obrigatórios.")
                return
            lgpd_ts = record_lgpd_consent(email)
            if db.create_professional(email, password, name, specialty, crn, lgpd_ts):
                pro = db.get_professional(email, password)
                if pro:
                    st.session_state.professional = pro.to_dict()
                    st.session_state.page = "pro_dashboard"
                    try:
                        send_welcome(email, name, config.TRIAL_DAYS)
                    except Exception:
                        pass
                    st.success("✅ Conta profissional criada!")
                    st.rerun()
            else:
                st.error("❌ Email já cadastrado.")
