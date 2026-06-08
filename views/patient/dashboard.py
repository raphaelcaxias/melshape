"""
Melshape — Dashboard com @st.fragment nos gráficos
e @st.cache_data nos resumos pesados.
"""
import streamlit as st
from datetime import date
from views.components import (
    metric_card, progress_bar, empty_state, section_header,
    calories_area_chart, macros_pie_chart, weight_line_chart,
    period_bar_chart, protein_week_chart,
    show_clinical_alerts, medical_disclaimer,
)


# ── Cache do resumo semanal (5 min) ───────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _cached_weekly(user_email: str, _db):
    import pandas as pd
    from datetime import timedelta
    meals = [m for m in _db._mock().get("meals", []) if m.get("user_id") == user_email]
    if not meals:
        return pd.DataFrame()
    import datetime as dt
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    meals  = [m for m in meals if m.get("meal_date","") >= cutoff]
    if not meals:
        return pd.DataFrame()
    df = __import__("pandas").DataFrame([{
        "date": m["meal_date"], "calories": m.get("calories",0),
        "protein": m.get("protein",0),
    } for m in meals])
    df["date"] = __import__("pandas").to_datetime(df["date"])
    return (df.groupby(df["date"].dt.date)
              .agg(calories=("calories","sum"), protein=("protein","sum"))
              .reset_index())


@st.cache_data(ttl=600, show_spinner=False)
def _cached_period(user_email: str, _db) -> dict:
    from datetime import timedelta
    meals = [m for m in _db._mock().get("meals", []) if m.get("user_id") == user_email]
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    meals  = [m for m in meals if m.get("meal_date","") >= cutoff]
    periods = {"Manhã": 0, "Tarde": 0, "Noite": 0}
    for m in meals:
        t = m.get("meal_time","")
        if not t:
            continue
        try:
            h = int(t.split(":")[0])
        except Exception:
            continue
        p = "Manhã" if h < 12 else "Tarde" if h < 18 else "Noite"
        periods[p] += m.get("calories", 0)
    return {"calories_by_period": periods}


# ── Fragment: gráfico de calorias semanais ────────────────────────────────────
@st.fragment
def _weekly_chart_fragment(user_email: str, meta: int, db) -> None:
    st.markdown("**📈 Calorias — Últimos 7 Dias**")
    wk = _cached_weekly(user_email, db)
    if not wk.empty:
        calories_area_chart(wk, meta)
    else:
        empty_state("📊", "Sem dados", "Registre por 2+ dias")


# ── Fragment: macros de hoje ──────────────────────────────────────────────────
@st.fragment
def _macros_fragment(protein: float, carbs: float, fat: float) -> None:
    st.markdown("**🥗 Macros de Hoje**")
    if protein + carbs + fat > 0:
        macros_pie_chart(protein, carbs, fat)
    else:
        empty_state("🥗", "Sem refeições hoje")


# ── Fragment: proteína semanal ────────────────────────────────────────────────
@st.fragment
def _protein_fragment(user_email: str, prot_goal: float, db) -> None:
    st.markdown("**🥩 Proteína — Últimos 7 Dias**")
    wk = _cached_weekly(user_email, db)
    if not wk.empty and "protein" in wk.columns:
        protein_week_chart(wk, prot_goal)
    else:
        empty_state("🥩", "Sem dados de proteína")


# ── Fragment: gráfico de peso ─────────────────────────────────────────────────
@st.fragment
def _weight_fragment(db, goal_weight) -> None:
    st.markdown("**⚖️ Evolução de Peso**")
    df_w = db.get_weights(90)
    if not df_w.empty and len(df_w) >= 2:
        weight_line_chart(df_w, goal_weight)
    else:
        empty_state("⚖️", "Registre seu peso para ver o gráfico")


# ── Fragment: análise de período ──────────────────────────────────────────────
@st.fragment
def _period_fragment(user_email: str, db) -> None:
    st.markdown("**🕐 Calorias por Período (30 dias)**")
    pd_data = _cached_period(user_email, db)
    if any(v > 0 for v in pd_data["calories_by_period"].values()):
        period_bar_chart(pd_data["calories_by_period"])
    else:
        empty_state("🕐", "Sem dados de período")


def render(services: dict, user: dict) -> None:
    nutrition    = services["nutrition"]
    gamification = services["gamification"]
    db           = services["db"]
    plan_svc     = services["plan"]

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    section_header("📊 Dashboard", f"Visão completa · {date.today().strftime('%d/%m/%Y')}")

    plan_svc.trial_banner(user)

    if not plan_svc.can_use(user, "charts"):
        plan_svc.show_paywall("Dashboard com gráficos", user)
        medical_disclaimer()
        return

    show_clinical_alerts(services, user)

    sm          = nutrition.daily_summary()
    streak      = gamification.streak()
    w           = float(user.get("current_weight") or 70.0)
    g_w         = float(user.get("goal_weight") or 65.0)
    consist     = nutrition.consistency_score()
    lvl         = gamification.level()
    prot_goal   = nutrition.calc_protein_goal(w, user.get("health_mode","general"))
    user_email  = user.get("email","")

    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        prot_color = "green" if sm["protein"] >= prot_goal * 0.8 else "red"
        metric_card(f"{sm['protein']:.0f}g", "Proteínas Hoje", "🥩", prot_color)
    with c2:
        metric_card(f"{sm['calories']} kcal", "Calorias Hoje", "🔥")
    with c3:
        metric_card(f"{streak} dias", "Sequência", "📅", "carbon")
    with c4:
        metric_card(f"{consist}%", "Consistência 30d", "✅", "steel")

    st.markdown("")

    tmb  = nutrition.calc_tmb(w, user.get("height"), user.get("age"),
                               user.get("gender","female"))
    meta = nutrition.calc_goal_calories(
        tmb, user.get("activity_level","moderate"),
        user.get("goal","lose"), user.get("health_mode","general"),
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🥩 Proteína Diária (prioridade)**")
        progress_bar(sm["protein"], prot_goal,
                     f"{sm['protein']:.0f}g", f"Meta: {prot_goal:.0f}g", "green")
    with c2:
        st.markdown("**🎯 Calorias Diárias**")
        progress_bar(sm["calories"], meta, f"{sm['calories']} kcal", f"Meta: {meta}")

    st.markdown("---")

    # Gráficos via fragments — cada um re-renderiza independentemente
    c1, c2 = st.columns([3, 2])
    with c1:
        _weekly_chart_fragment(user_email, meta, db)
    with c2:
        _macros_fragment(sm["protein"], sm["carbs"], sm["fat"])

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        _protein_fragment(user_email, prot_goal, db)
    with c2:
        _weight_fragment(db, g_w if g_w else None)

    st.markdown("---")
    _period_fragment(user_email, db)

    # Exportação
    st.markdown("---")
    if plan_svc.can_use(user, "export"):
        st.markdown("**💾 Exportar Dados**")
        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            st.download_button(
                "📥 Refeições CSV",
                db.export_meals_csv(),
                f"melshape_refeicoes_{date.today()}.csv",
                "text/csv", use_container_width=True,
            )
        with c2:
            st.download_button(
                "📥 Peso CSV",
                db.export_weights_csv(),
                f"melshape_peso_{date.today()}.csv",
                "text/csv", use_container_width=True,
            )
    else:
        st.caption("💾 Exportação disponível no plano Pro.")

    medical_disclaimer()
    st.markdown('</div>', unsafe_allow_html=True)
