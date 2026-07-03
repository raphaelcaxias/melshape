"""
Melshape — Perfil: tabs de plano, preferências e conta.

Importado por profile.py:
    from views.patient.profile_tabs import _tab_plano, _tab_preferencias, _tab_conta

Cada função recebe apenas os argumentos que profile.py passa:
    _tab_plano(self.plan_svc, self.user)
    _tab_preferencias(self.db, self.user)
    _tab_conta(self.db, self.user)
"""
from __future__ import annotations

import logging
from typing import Any

import streamlit as st

import config

logger = logging.getLogger("Melshape.ProfileTabs")


# ─────────────────────────────────────────────────────────────────────────────
# TAB PLANO
# ─────────────────────────────────────────────────────────────────────────────

_PLAN_INFO: dict[str, dict[str, str]] = {
    "free":     {"icon": "🔓", "label": "Gratuito",  "desc": "Funcionalidades básicas"},
    "trial":    {"icon": "✨", "label": "Trial",      "desc": f"{config.TRIAL_DAYS} dias de acesso completo"},
    "pro":      {"icon": "🚀", "label": "Pro",        "desc": "Acesso completo e sem limites"},
    "lifetime": {"icon": "👑", "label": "Vitalício",  "desc": "Acesso permanente"},
    "clinic":   {"icon": "🏥", "label": "Clínica",   "desc": "Gestão de equipe e pacientes"},
}


def _tab_plano(plan_svc: Any, user: dict[str, Any]) -> None:
    """Renderiza aba de plano do usuário.

    Args:
        plan_svc: Instância do PlanService (pode ser None em mock).
        user:     Dados do usuário logado.
    """
    st.markdown("##### 💳 Meu Plano")

    if not plan_svc:
        st.info("ℹ️ Gerenciamento de planos em breve.")
        return

    try:
        plan = plan_svc.get_plan(user)
    except Exception:
        plan = user.get("plan", "free")

    info = _PLAN_INFO.get(plan, _PLAN_INFO["free"])

    st.markdown(
        f"""
        <div class="metric-card fade-in" style="margin-bottom: 1rem;">
            <div style="display: flex; align-items: center; gap: 0.8rem;">
                <span style="font-size: 2rem;">{info['icon']}</span>
                <div>
                    <div style="font-weight: 800; font-size: 1.1rem; color: var(--text);">
                        {info['icon']} {info['label']}
                    </div>
                    <div style="font-size: 0.80rem; color: var(--text-muted);">
                        {info['desc']}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if plan == "trial":
        try:
            days = plan_svc.trial_days_remaining(user)
            if days > 0:
                st.progress(
                    days / config.TRIAL_DAYS,
                    text=f"⏳ {days} dia(s) restante(s) de trial",
                )
            else:
                st.warning("⏳ Trial expirado. Assine o Pro para continuar.")
        except Exception:
            pass

    if plan in ("free", "trial"):
        try:
            from services.payment_service import PaymentService
            pay_svc = PaymentService(db)
            user_email = user.get("email", "")
            user_name = user.get("name", "")

            if pay_svc.is_configured:
                html = pay_svc.get_checkout_button_html(
                    user_email, user_name, plan="pro",
                    label="🚀 Assinar Melshape Pro",
                )
                st.markdown(html, unsafe_allow_html=True)
            else:
                # MP não configurado — mostra botão desativado com instrução
                st.markdown(
                    """
                    <div style="background:var(--surface-2);border:1px solid var(--border);
                        border-radius:var(--radius-md);padding:1rem;text-align:center;">
                        <div style="font-weight:700;color:var(--text);margin-bottom:.4rem;">
                            🚀 Melshape Pro
                        </div>
                        <div style="font-size:.82rem;color:var(--text-muted);">
                            Configure <code>MP_ACCESS_TOKEN</code> no <code>.env</code>
                            para ativar o pagamento.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        except Exception as _pe:
            st.info("🔜 Pagamento em configuração. Entre em contato pelo suporte.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB PREFERÊNCIAS
# ─────────────────────────────────────────────────────────────────────────────

def _tab_preferencias(db: Any, user: dict[str, Any]) -> None:
    """Renderiza aba de preferências do usuário.

    Args:
        db:   Instância do Database.
        user: Dados do usuário logado.
    """
    st.markdown("##### 🔔 Preferências")

    dark_mode = st.toggle(
        "🌙 Modo escuro",
        value=bool(user.get("dark_mode", False)),
        key="pf_dark_mode",
    )

    if dark_mode != bool(user.get("dark_mode", False)):
        try:
            db.update_user({"dark_mode": dark_mode})
            st.session_state.user["dark_mode"] = dark_mode
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao salvar dark_mode: {e}")
            st.error("❌ Erro ao salvar preferência.")

    st.markdown("---")
    st.markdown("##### 📧 Notificações")
    st.info("🔜 Configuração de notificações por e-mail em breve.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB CONTA
# ─────────────────────────────────────────────────────────────────────────────

_SESSION_KEYS_TO_CLEAR = [
    "user", "professional", "perfil_id", "page",
    "demo_loaded", "onboarding_step", "onboarding_mode",
    "ci_result", "cs_resumo", "hub_tipo",
]


def _tab_conta(db: Any, user: dict[str, Any]) -> None:
    """Renderiza aba de conta do usuário (logout + exclusão).

    Args:
        db:   Instância do Database.
        user: Dados do usuário logado.
    """
    st.markdown("##### 🚪 Conta")

    if st.button("🚪 Sair", use_container_width=True, key="pf_sair"):
        _clear_session()
        return

    st.markdown("---")
    st.markdown("##### ⚠️ Área de Risco")

    with st.expander("🗑️ Excluir conta (irreversível)"):
        st.warning(
            "⚠️ Esta ação é **permanente e irreversível**. "
            "Todos os seus dados serão apagados em 30 dias conforme a LGPD."
        )
        confirmacao = st.text_input(
            "Digite **EXCLUIR** para confirmar",
            key="pf_confirmar_exclusao",
        )
        if st.button(
            "✅ Confirmar exclusão",
            type="primary",
            use_container_width=True,
            key="pf_excluir_conta",
            disabled=(confirmacao != "EXCLUIR"),
        ):
            email = user.get("email", "")
            try:
                if email and db.delete_user(email):
                    st.success("✅ Conta excluída conforme LGPD.")
                    _clear_session()
                else:
                    st.error("❌ Erro ao excluir conta. Tente mais tarde.")
            except Exception as e:
                logger.error(f"Erro ao excluir conta: {e}")
                st.error("❌ Erro ao excluir conta.")


def _clear_session() -> None:
    """Limpa a sessão e redireciona para a landing page."""
    for key in _SESSION_KEYS_TO_CLEAR:
        st.session_state.pop(key, None)
    st.session_state.page = "landing"
    st.rerun()
