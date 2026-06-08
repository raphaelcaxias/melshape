"""Melshape — Recuperação de senha com token por email."""
import streamlit as st
from services.email_service import request_password_reset, consume_reset_token
from core.security import hash_password, validate_email, validate_password


def render(services: dict) -> None:
    """Renderiza o fluxo completo de recuperação de senha."""
    db = services["db"]

    # ── Verifica se veio de link de reset na URL ──────────────────────────
    params = st.query_params
    if "reset_token" in params and "email" in params:
        _render_new_password(db, params["email"], params["reset_token"])
        return

    # ── Formulário de solicitação ─────────────────────────────────────────
    st.markdown(
        '<div class="hero-banner" style="padding:1.5rem 2rem;">'
        '<h2 style="font-size:1.5rem;margin:0;">🔒 Recuperar Senha</h2>'
        '<p style="margin:0.3rem 0 0;opacity:0.9;">Enviaremos um link para seu email.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.get("reset_email_sent"):
        st.success(
            "✅ Email enviado! Verifique sua caixa de entrada e spam. "
            "O link expira em **15 minutos**."
        )
        if st.button("← Voltar ao Login", use_container_width=True):
            st.session_state.pop("reset_email_sent", None)
            st.session_state.page = "login"
            st.rerun()
        return

    with st.form("forgot_password_form", clear_on_submit=False):
        st.markdown("#### Digite seu email cadastrado")
        email = st.text_input("Email", placeholder="seu@email.com")

        if st.form_submit_button("Enviar link de recuperação →",
                                  type="primary", use_container_width=True):
            valid, msg = validate_email(email)
            if not valid:
                st.error(msg)
                return

            # Busca usuário no MockDB
            users = st.session_state.mock_db.get("users", {})
            user  = users.get(email.lower())

            if user:
                name = user.get("name", email.split("@")[0])
                base_url = st.secrets.get("APP_URL", "http://localhost:8501")
                request_password_reset(email.lower(), name, base_url)

            # Sempre mostra sucesso (segurança: não revelar se email existe)
            st.session_state.reset_email_sent = True
            st.rerun()

    st.markdown("")
    if st.button("← Voltar", use_container_width=True):
        st.session_state.page = "login"
        st.rerun()


def _render_new_password(db, email: str, token: str) -> None:
    """Renderiza formulário de nova senha após validar token."""
    from services.email_service import validate_reset_token

    st.markdown(
        '<div class="hero-banner" style="padding:1.5rem 2rem;">'
        '<h2 style="font-size:1.5rem;margin:0;">🔒 Criar Nova Senha</h2>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not validate_reset_token(email, token):
        st.error("❌ Link inválido ou expirado. Solicite um novo link de recuperação.")
        if st.button("Solicitar novo link", type="primary", use_container_width=True):
            st.query_params.clear()
            st.session_state.page = "forgot_password"
            st.rerun()
        return

    with st.form("new_password_form", clear_on_submit=False):
        st.markdown(f"**Redefinindo senha para:** `{email}`")
        password  = st.text_input("Nova senha (mín. 6 caracteres)", type="password")
        password2 = st.text_input("Confirmar nova senha", type="password")

        if st.form_submit_button("Salvar nova senha →",
                                  type="primary", use_container_width=True):
            if password != password2:
                st.error("As senhas não coincidem.")
                return
            ok, msg = validate_password(password)
            if not ok:
                st.error(msg)
                return

            # Consome token e atualiza senha
            if consume_reset_token(email, token):
                users = st.session_state.mock_db.get("users", {})
                if email.lower() in users:
                    users[email.lower()]["password_hash"] = hash_password(password)
                    st.query_params.clear()
                    st.success("✅ Senha redefinida com sucesso! Faça login.")
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.error("Usuário não encontrado.")
            else:
                st.error("Token inválido. Solicite um novo link.")
