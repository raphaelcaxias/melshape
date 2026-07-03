"""
Melshape — Onboarding do Profissional.

Hoje o profissional cai direto num dashboard vazio sem direção.
Esta tela resolve isso com 3 passos objetivos:
  1. Boas-vindas — o que o Melshape faz por ele
  2. Convidar o primeiro paciente — ação concreta imediata
  3. Conhecer o resumo pré-consulta — o diferencial real do produto

Constituição:
- Cap. VI: Uma Única Ação Principal por tela
- Cap. IV: O Profissional precisa economizar tempo e tomar decisões claras
- Auditoria Mestra (Auditoria 6): "Não há onboarding do profissional —
  taxa de ativação deve ser baixíssima por isso"
"""
from __future__ import annotations

import logging
from typing import Any

import streamlit as st

import config

logger = logging.getLogger("Melshape.OnboardingPro")

_TOTAL_STEPS = 3


class OnboardingProRenderer:
    def __init__(self, services: dict[str, Any], professional: Any) -> None:
        self.services = services
        self.db = services.get("db")
        self.professional = professional
        self.pro_name = (
            professional.name if hasattr(professional, "name")
            else professional.get("name", "Profissional")
        ).split()[0]
        self.pro_email = (
            professional.email if hasattr(professional, "email")
            else professional.get("email", "")
        )

    def render(self) -> None:
        step = st.session_state.get("pro_onboarding_step", 1)

        pct = int((step - 1) / _TOTAL_STEPS * 100)
        st.markdown(
            f"""
            <div style="margin-bottom:1.6rem;">
                <div style="display:flex;justify-content:space-between;
                    font-size:0.76rem;color:var(--text-muted);margin-bottom:0.4rem;">
                    <span>Passo {step} de {_TOTAL_STEPS}</span>
                    <span>{pct}%</span>
                </div>
                <div class="progress-track">
                    <div class="progress-fill" style="width:{pct}%;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if step == 1:
            self._step_boas_vindas()
        elif step == 2:
            self._step_convite()
        elif step == 3:
            self._step_resumo_consulta()
        else:
            self._finalizar()

    # ── PASSO 1 — Boas-vindas ────────────────────────────────────────────────

    def _step_boas_vindas(self) -> None:
        st.markdown(
            f"""
            <div style="text-align:center;padding:1rem 0 1.5rem;">
                <div style="font-size:2.8rem;margin-bottom:0.6rem;">👨‍⚕️</div>
                <h2 style="font-family:var(--font-display);font-weight:800;
                    color:var(--text);margin-bottom:0.3rem;">
                    Bem-vindo(a), Dr(a). {self.pro_name}
                </h2>
                <p style="color:var(--text-muted);font-size:0.94rem;
                    max-width:380px;margin:0 auto;line-height:1.6;">
                    O {config.APP_NAME} foi feito para economizar seu tempo —
                    não para criar mais uma tela para você gerenciar.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        beneficios = [
            ("🚨", "Alertas automáticos", "Você é avisado quando um paciente precisa de atenção — sem precisar caçar a informação."),
            ("📄", "Resumo pré-consulta em 1 clique", "Peso, nutrição, hábitos e alertas dos últimos 30 dias, prontos antes de cada consulta."),
            ("🔗", "Convide pacientes em segundos", "Um link, sem fricção — o paciente cria a conta já vinculado a você."),
        ]

        for icon, titulo, desc in beneficios:
            st.markdown(
                f"""
                <div style="display:flex;gap:0.9rem;align-items:flex-start;
                    padding:0.85rem 1rem;background:var(--surface);
                    border:1px solid var(--border);border-radius:var(--radius-md);
                    margin-bottom:0.6rem;">
                    <span style="font-size:1.5rem;">{icon}</span>
                    <div>
                        <div style="font-weight:700;font-size:0.92rem;
                            color:var(--text);">{titulo}</div>
                        <div style="font-size:0.82rem;color:var(--text-muted);
                            margin-top:0.15rem;line-height:1.4;">{desc}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Continuar →", type="primary", use_container_width=True,
                     key="pro_ob_p1"):
            st.session_state.pro_onboarding_step = 2
            st.rerun()

    # ── PASSO 2 — Convidar primeiro paciente ─────────────────────────────────

    def _step_convite(self) -> None:
        st.markdown(
            """
            <div style="text-align:center;padding:0.5rem 0 1.2rem;">
                <div style="font-size:2.2rem;margin-bottom:0.5rem;">🔗</div>
                <h2 style="font-family:var(--font-display);font-weight:800;
                    color:var(--text);margin-bottom:0.3rem;">
                    Convide seu primeiro paciente
                </h2>
                <p style="color:var(--text-muted);font-size:0.88rem;
                    max-width:360px;margin:0 auto;">
                    Gere um link agora — leva 10 segundos. Você pode pular
                    e fazer isso depois, mas o app só ganha valor com
                    pacientes vinculados.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        try:
            from professional.patient_invite import InviteService
            inv_svc = InviteService(self.db)

            if st.button("🔗 Gerar meu primeiro link de convite",
                         type="primary", use_container_width=True,
                         key="pro_ob_gerar_convite"):
                convite = inv_svc.gerar(self.pro_email)
                if convite:
                    st.session_state["pro_ob_convite"] = convite
                    st.cache_data.clear()

            convite = st.session_state.get("pro_ob_convite")
            if convite:
                st.markdown(
                    f"""
                    <div style="background:var(--success-bg);
                        border:1px solid var(--success-border);
                        border-radius:var(--radius-md);padding:0.9rem 1rem;
                        margin-top:0.8rem;">
                        <div style="font-size:0.76rem;color:var(--success);
                            font-weight:700;text-transform:uppercase;
                            letter-spacing:.04em;margin-bottom:0.3rem;">
                            ✅ Link gerado
                        </div>
                        <div style="font-family:monospace;font-size:0.78rem;
                            color:var(--text);word-break:break-all;">
                            {convite.link}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.caption("💡 Copie e envie pelo WhatsApp ou e-mail. "
                           "Você também encontra esse link a qualquer momento "
                           "em 'Convidar Pacientes' na barra lateral.")
        except Exception as e:
            logger.error(f"_step_convite: {e}")
            st.info("Você poderá convidar pacientes a qualquer momento pelo menu lateral.")

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Pular por agora", use_container_width=True,
                         key="pro_ob_p2_skip"):
                st.session_state.pro_onboarding_step = 3
                st.rerun()
        with col2:
            if st.button("Continuar →", type="primary",
                         use_container_width=True, key="pro_ob_p2_next"):
                st.session_state.pro_onboarding_step = 3
                st.rerun()

    # ── PASSO 3 — Resumo pré-consulta ────────────────────────────────────────

    def _step_resumo_consulta(self) -> None:
        st.markdown(
            """
            <div style="text-align:center;padding:0.5rem 0 1.2rem;">
                <div style="font-size:2.2rem;margin-bottom:0.5rem;">📄</div>
                <h2 style="font-family:var(--font-display);font-weight:800;
                    color:var(--text);margin-bottom:0.3rem;">
                    Seu maior diferencial: o Resumo Pré-Consulta
                </h2>
                <p style="color:var(--text-muted);font-size:0.88rem;
                    max-width:380px;margin:0 auto;line-height:1.6;">
                    Antes de cada consulta, abra o resumo do paciente.
                    Em segundos você vê tudo que aconteceu nos últimos 30 dias —
                    sem perguntar, sem adivinhar.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="metric-card fade-in" style="background:var(--primary-light);
                border-color:var(--primary-border);">
                <div style="font-size:0.84rem;color:var(--text);line-height:1.7;">
                    📊 Variação de peso e nutrição<br>
                    ✅ Aderência aos hábitos e check-ins<br>
                    ⚠️ Alertas clínicos que precisam de atenção<br>
                    🏅 Engajamento e conquistas
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 Ir para meu painel", type="primary",
                     use_container_width=True, key="pro_ob_finalizar"):
            self._finalizar()

    def _finalizar(self) -> None:
        try:
            if hasattr(self.db, "update_professional"):
                self.db.update_professional(self.pro_email, {"onboarding_done": True})
        except Exception as e:
            logger.warning(f"_finalizar onboarding: {e}")

        st.session_state["professional"]["onboarding_done"] = True
        for k in ["pro_onboarding_step", "pro_ob_convite"]:
            st.session_state.pop(k, None)
        st.session_state.page = "pro_dashboard"
        st.rerun()


def render(services: dict[str, Any], professional: Any) -> None:
    OnboardingProRenderer(services, professional).render()
