"""Melshape — Treino do dia com ajuste calórico automático."""
import streamlit as st
from datetime import date
from core.models import WorkoutLog
from core.models.workout import WORKOUT_TYPES, MUSCLE_GROUPS
from views.components import empty_state, section_header, medical_disclaimer


def render(services: dict, user: dict) -> None:
    db       = services["db"]
    plan_svc = services["plan"]

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    section_header("🏋️ Treino do Dia", "Ajuste automático da meta calórica")

    if not plan_svc.can_use(user, "workout"):
        plan_svc.show_paywall("Registro de Treino", user)
        medical_disclaimer()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Treino atual
    workout_hoje = db.get_workout_today()
    if workout_hoje:
        adj = workout_hoje.calorie_adjustment()
        wt  = WORKOUT_TYPES.get(workout_hoje.workout_type, workout_hoje.workout_type)
        mg  = MUSCLE_GROUPS.get(workout_hoje.muscle_group, "")
        st.markdown(
            f'<div class="alert-success">'
            f'✅ <b>Treino de hoje:</b> {wt} · {mg} · {workout_hoje.intensity} · '
            f'{workout_hoje.duration_min} min'
            f'{"  · Meta: <b>+" + str(adj) + " kcal</b>" if adj > 0 else " · Meta reduzida (descanso)"}'
            f'</div>',
            unsafe_allow_html=True,
        )

    with st.form("workout_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            workout_type = st.selectbox(
                "Tipo de treino",
                list(WORKOUT_TYPES.keys()),
                format_func=lambda x: WORKOUT_TYPES[x],
            )
            muscle_group = st.selectbox(
                "Grupo muscular",
                list(MUSCLE_GROUPS.keys()),
                format_func=lambda x: MUSCLE_GROUPS[x],
            )
        with c2:
            intensity = st.selectbox(
                "Intensidade",
                ["light", "moderate", "heavy"],
                index=1,
                format_func=lambda x: {
                    "light":    "🟢 Leve",
                    "moderate": "🟡 Moderada",
                    "heavy":    "🔴 Pesada",
                }[x],
            )
            duration = st.number_input("Duração (minutos)", 0, 300, 60, 5)
            notes    = st.text_input("Observações (opcional)")

        # Preview do ajuste
        temp_w  = WorkoutLog(workout_type=workout_type, intensity=intensity, duration_min=duration)
        adj_pre = temp_w.calorie_adjustment()
        if adj_pre > 0:
            st.markdown(
                f'<div class="alert-info">⚡ Este treino adiciona '
                f'<b>+{adj_pre} kcal</b> à sua meta de hoje.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="alert-warning">😴 Dia de descanso: meta calórica '
                'reduzida em 100 kcal.</div>',
                unsafe_allow_html=True,
            )

        if st.form_submit_button("💾 Salvar Treino", type="primary", use_container_width=True):
            w = WorkoutLog(
                workout_type=workout_type, muscle_group=muscle_group,
                intensity=intensity, duration_min=duration, notes=notes,
                log_date=date.today().isoformat(),
            )
            db.save_workout(w)
            st.success(
                f"✅ Treino salvo! Meta ajustada em {w.calorie_adjustment():+d} kcal."
            )
            st.rerun()

    # Histórico
    st.markdown("---")
    st.markdown("**📅 Últimos 7 dias**")
    workouts = db.get_workouts(7)
    if workouts:
        for w in sorted(workouts, key=lambda x: x.log_date, reverse=True):
            wt  = WORKOUT_TYPES.get(w.workout_type, w.workout_type)
            mg  = MUSCLE_GROUPS.get(w.muscle_group, "")
            adj = w.calorie_adjustment()
            st.markdown(
                f'<div class="supl-item">'
                f'<div><b>{w.log_date}</b> · {wt} {mg}</div>'
                f'<div style="color:#C9A84C;">{w.intensity} · {w.duration_min}min · {adj:+d} kcal</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        empty_state("🏋️", "Nenhum treino registrado", "Comece agora!")

    medical_disclaimer()
    st.markdown('</div>', unsafe_allow_html=True)
