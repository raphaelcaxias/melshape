"""Melshape — Controle de peso com % gordura e massa muscular."""
import streamlit as st
from datetime import date
from core.models import WeightLog
from views.components import (
    empty_state, metric_card, section_header,
    show_new_achievements, weight_line_chart, medical_disclaimer,
)


def render(services: dict, user: dict) -> None:
    db           = services["db"]
    gamification = services["gamification"]

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    section_header("⚖️ Evolução de Peso", "Registre e acompanhe sua jornada")

    c1, c2 = st.columns([1, 2])

    with c1:
        st.markdown("**📝 Nova Pesagem**")
        peso    = st.number_input("Peso (kg)", 30.0, 300.0,
                                  float(user.get("current_weight") or 70.0), 0.1)
        dt      = st.date_input("Data", value=date.today())
        gordura = st.number_input("% Gordura corporal (opcional)", 0.0, 60.0, 0.0, 0.1)
        musculo = st.number_input("Massa muscular kg (opcional)", 0.0, 150.0, 0.0, 0.1)
        notas   = st.text_area("Observações")

        if st.button("💾 Salvar Pesagem", type="primary", use_container_width=True):
            log = WeightLog(
                weight=peso, log_date=dt.isoformat(), notes=notas,
                body_fat=gordura, muscle_mass=musculo,
            )
            db.save_weight(log)
            user["current_weight"] = peso
            st.session_state.user  = user
            st.success(f"✅ {peso:.1f} kg registrado!")
            show_new_achievements(gamification.check_achievements(user))
            st.rerun()

        g = user.get("goal_weight")
        if g:
            diff  = peso - float(g)
            color = "#dc2626" if diff > 0 else "#16a34a"
            st.markdown(
                f'<div style="background:#f8fafc;border-radius:10px;padding:0.9rem;'
                f'text-align:center;margin-top:0.75rem;">'
                f'<div style="font-size:0.78rem;color:#64748b;">Meta: {g:.1f} kg</div>'
                f'<div style="font-family:Sora,sans-serif;font-size:1.3rem;font-weight:700;color:{color};">'
                f'{abs(diff):.1f} kg {"acima" if diff > 0 else "abaixo"} da meta'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    with c2:
        periodo = st.selectbox("📅 Período", ["30 dias", "60 dias", "90 dias"])
        days    = {"30 dias": 30, "60 dias": 60, "90 dias": 90}[periodo]
        df      = db.get_weights(days)

        if not df.empty and len(df) >= 1:
            weight_line_chart(df, user.get("goal_weight"))

            if len(df) >= 2:
                primeiro = float(df.iloc[0]["weight"])
                atual    = float(df.iloc[-1]["weight"])
                variacao = atual - primeiro
                total_d  = max(1, (df.iloc[-1]["log_date"] - df.iloc[0]["log_date"]).days)

                c1b, c2b, c3b, c4b = st.columns(4)
                with c1b:
                    metric_card(f"{primeiro:.1f} kg", f"Inicial ({days}d)", "📌")
                with c2b:
                    metric_card(f"{atual:.1f} kg", "Atual", "⚖️", "steel")
                with c3b:
                    metric_card(f"{variacao:+.1f} kg", "Variação", "📉",
                                "green" if variacao < 0 else "red")
                with c4b:
                    speed = variacao / (total_d / 7)
                    metric_card(f"{speed:+.2f} kg/sem", "Velocidade", "⚡")
        else:
            empty_state("⚖️", "Nenhuma pesagem", "Adicione a primeira pesagem!")

    medical_disclaimer()
    st.markdown('</div>', unsafe_allow_html=True)
