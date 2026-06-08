"""Melshape — Vitrine pública (showcase do produto)."""
import streamlit as st
from views.components import feature_card, section_header


def render() -> None:
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    section_header("🔥 Melshape — Showcase", "Para quem está mudando de verdade.")

    st.markdown("### 🎯 Para quem é o Melshape?")
    c1, c2 = st.columns(2)
    with c1:
        feature_card("💉","Usuários de GLP-1",
                     "Ozempic, Mounjaro, Wegovy. Monitore proteína, hidratação e sintomas.")
        feature_card("🔪","Pós-Bariátrica",
                     "Fases, volumes, suplementos essenciais do líquido à manutenção.")
    with c2:
        feature_card("🏋️","Fitness & Atletas",
                     "Meta calórica adaptável ao treino do dia. Protocolo de macros.")
        feature_card("⚖️","Emagrecimento",
                     "Déficit inteligente, consistência e gamificação real.")

    st.markdown("---")
    st.markdown("### 🏥 Para Profissionais de Saúde")
    feature_card("🩺","Painel Profissional",
                 "Triagem clínica automática, acompanhamento de pacientes em tempo real, "
                 "alertas de risco e exportação de relatórios.")

    st.markdown("---")
    st.markdown("### 💰 Planos")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            '<div style="background:#f8fafc;border:1px solid #e8e0d0;border-radius:14px;'
            'padding:1.25rem;text-align:center;">'
            '<b>🆓 Free</b><br>3 refeições/dia<br>7 dias histórico<br><b>Grátis</b>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div style="background:rgba(201,168,76,.08);border:2px solid #C9A84C;border-radius:14px;'
            'padding:1.25rem;text-align:center;">'
            '<b>⭐ Pro</b><br>Ilimitado · GLP-1 · Bariátrico<br>Treino · Sono · Export<br>'
            '<b>R$19,90/mês</b>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div style="background:#1C1C1E12;border:1px solid #1C1C1E30;border-radius:14px;'
            'padding:1.25rem;text-align:center;">'
            '<b>👑 Vitalício</b><br>Tudo para sempre<br>Sem mensalidade<br><b>R$197 único</b>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    if st.button("🎮 Experimentar Demo Agora", use_container_width=True, type="primary"):
        st.session_state.page = "landing"
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
