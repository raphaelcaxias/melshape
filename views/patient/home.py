"""Melshape — Home do paciente com hidratação rápida, alertas clínicos e sono."""
import streamlit as st
from datetime import date, datetime
from views.components import (
    metric_card, progress_bar, alert, empty_state,
    meal_item, show_new_achievements, section_header,
    motivational_quote, hydration_bar, medical_disclaimer,
    show_clinical_alerts,
)
from utils.date_helpers import get_greeting
from utils.motivational_quotes import get_quote
import config


def render(services: dict, user: dict) -> None:
    nutrition    = services["nutrition"]
    gamification = services["gamification"]
    plan_svc     = services["plan"]
    db           = services["db"]

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)

    # Trial banner
    plan_svc.trial_banner(user)

    # Saudação
    greeting = get_greeting(user.get("name", ""))
    mode_label = {
        "general": "Emagrecimento ⚖️", "bariatric": "Pós-Bariátrica 🔪",
        "glp1": "GLP-1 💉", "fitness": "Fitness 🏋️",
    }.get(user.get("health_mode", "general"), "")

    st.markdown(
        f'<div class="hero-banner" style="padding:1.85rem 2rem;">'
        f'<h1 style="font-size:1.85rem;">{greeting}</h1>'
        f'<p>Modo: <b>{mode_label}</b> · {date.today().strftime("%d/%m/%Y")}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Conquistas
    unlocked = gamification.check_achievements(user)
    show_new_achievements(unlocked)

    # Alertas clínicos
    show_clinical_alerts(services, user)

    # Dados
    sm         = nutrition.daily_summary()
    streak     = gamification.streak()
    w          = float(user.get("current_weight") or 70.0)
    g_w        = float(user.get("goal_weight") or 65.0)
    hydration  = db.get_hydration_today()
    prot_goal  = nutrition.calc_protein_goal(w, user.get("health_mode", "general"))

    # ── 4 MÉTRICAS PRINCIPAIS (proteína em destaque #1) ───────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        prot_color = "green" if sm["protein"] >= prot_goal * 0.8 else "red"
        metric_card(f"{sm['protein']:.0f}g", "Proteínas Hoje", "🥩", prot_color)
    with c2:
        metric_card(f"{sm['calories']}", "Calorias Hoje", "🔥")
    with c3:
        metric_card(str(streak), "Dias Seguidos", "📅", "carbon")
    with c4:
        metric_card(f"{w:.1f} kg", "Peso Atual", "⚖️", "steel")

    st.markdown("")

    # ── METAS ─────────────────────────────────────────────────────────────
    workout     = db.get_workout_today()
    w_adj       = workout.calorie_adjustment() if workout else 0
    tmb         = nutrition.calc_tmb(w, user.get("height"), user.get("age"),
                                     user.get("gender", "female"))
    meta        = nutrition.calc_goal_calories(
        tmb, user.get("activity_level", "moderate"),
        user.get("goal", "lose"), user.get("health_mode", "general"), w_adj,
    )

    col_cal, col_prot = st.columns(2)
    with col_cal:
        adj_txt = f" *(+{w_adj} kcal treino)*" if w_adj > 0 else ""
        st.markdown(f"**🎯 Meta calórica:** {meta} kcal{adj_txt}")
        progress_bar(sm["calories"], meta, f"{sm['calories']} kcal", f"Meta: {meta}")
        cal_a = nutrition.calorie_alert(sm["calories"], meta)
        if cal_a:
            kind = "danger" if (sm["calories"] >= meta or sm["calories"] < 800) else "warning"
            alert(cal_a, kind)

    with col_prot:
        st.markdown(f"**🥩 Meta proteica:** {prot_goal:.0f}g/dia")
        progress_bar(sm["protein"], prot_goal,
                     f"{sm['protein']:.0f}g", f"Meta: {prot_goal:.0f}g", "green")

    # ── HIDRATAÇÃO RÁPIDA ─────────────────────────────────────────────────
    st.markdown("---")
    col_hyd, col_sleep = st.columns(2)

    with col_hyd:
        st.markdown("**💧 Hidratação de Hoje**")
        hydration_bar(hydration, config.HYDRATION_GOAL_ML)

        if plan_svc.can_use(user, "hydration"):
            ml_opts = [150, 200, 300, 500]
            btn_cols = st.columns(len(ml_opts))
            for i, ml in enumerate(ml_opts):
                with btn_cols[i]:
                    if st.button(f"+{ml}ml", key=f"hyd_{ml}", use_container_width=True):
                        from core.models import HydrationLog
                        db.save_hydration(HydrationLog(
                            amount_ml=ml,
                            log_time=datetime.now().strftime("%H:%M"),
                        ))
                        st.rerun()
        else:
            plan_svc.show_paywall("Registro de Hidratação", user)

    with col_sleep:
        st.markdown("**😴 Sono de Hoje**")
        sleep_log = db.get_sleep_today()
        if sleep_log:
            quality_label = {1:"😖",2:"😕",3:"😐",4:"🙂",5:"😄"}.get(sleep_log.quality,"")
            st.markdown(
                f'<div style="background:#f0fdf4;border-radius:10px;padding:0.85rem;text-align:center;">'
                f'<div style="font-size:1.5rem;font-weight:700;color:#16a34a;">{sleep_log.hours:.1f}h</div>'
                f'<div style="font-size:0.85rem;color:#64748b;">Qualidade: {quality_label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            if plan_svc.can_use(user, "sleep"):
                with st.form("quick_sleep", clear_on_submit=True):
                    hours = st.slider("Horas de sono", 0.0, 12.0, 7.0, 0.5)
                    if st.form_submit_button("💾 Salvar", use_container_width=True):
                        from core.models import SleepLog
                        db.save_sleep(SleepLog(hours=hours))
                        st.rerun()
            else:
                empty_state("😴", "Ative o plano Pro", "para registrar o sono")

    # ── REFEIÇÕES DO DIA ──────────────────────────────────────────────────
    st.markdown("---")
    col_meals, col_actions = st.columns([3, 1])

    with col_meals:
        st.markdown("**🍽️ Refeições de Hoje**")
        if sm["meals"]:
            st.markdown(
                f'<div style="background:rgba(201,168,76,.08);border-radius:10px;'
                f'padding:0.65rem 1rem;margin-bottom:0.5rem;font-size:0.85rem;color:#78350f;">'
                f'🔥 {sm["calories"]} kcal · 🥩 {sm["protein"]:.0f}g · '
                f'🍚 {sm["carbs"]:.0f}g · 🧈 {sm["fat"]:.0f}g · 🌿 {sm["fiber"]:.0f}g fibra'
                f'</div>',
                unsafe_allow_html=True,
            )
            for m in sm["meals"]:
                meal_item(m.meal_time, m.food, m.calories, m.nutrient_score)
        else:
            empty_state("🍽️", "Nenhuma refeição hoje", "Registre agora!")

    with col_actions:
        st.markdown("**⚡ Ações Rápidas**")
        if st.button("🍴 Registrar Refeição", use_container_width=True, type="primary"):
            st.session_state.page = "meals"
            st.rerun()
        st.markdown("")
        if st.button("🏋️ Treino de Hoje", use_container_width=True):
            st.session_state.page = "workout"
            st.rerun()
        st.markdown("")
        if st.button("💊 Suplementos", use_container_width=True):
            st.session_state.page = "supplements"
            st.rerun()
        st.markdown("")
        if st.button("⚖️ Registrar Peso", use_container_width=True):
            st.session_state.page = "weight"
            st.rerun()

        # Treino do dia
        if workout:
            from core.models.workout import WORKOUT_TYPES
            wt = WORKOUT_TYPES.get(workout.workout_type, workout.workout_type)
            st.markdown(
                f'<div class="workout-badge" style="margin-top:0.65rem;">'
                f'<b>Treino:</b> {wt}<br>'
                f'{workout.intensity} · {workout.duration_min}min'
                f'{"  · <b>+" + str(w_adj) + " kcal</b>" if w_adj > 0 else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── FRASE MOTIVACIONAL ────────────────────────────────────────────────
    quote = get_quote("general", user.get("health_mode", "general"))
    motivational_quote(quote)

    medical_disclaimer()
    st.markdown('</div>', unsafe_allow_html=True)
