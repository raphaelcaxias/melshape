"""Melshape — Dashboard completo com proteína em destaque."""
import streamlit as st
from datetime import date
from views.components import (
    metric_card, progress_bar, empty_state, section_header,
    calories_area_chart, macros_pie_chart, weight_line_chart,
    period_bar_chart, protein_week_chart, show_clinical_alerts,
    medical_disclaimer,
)


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

    # Alertas clínicos no topo do dashboard
    show_clinical_alerts(services, user)

    sm      = nutrition.daily_summary()
    streak  = gamification.streak()
    w       = float(user.get("current_weight") or 70.0)
    g_w     = float(user.get("goal_weight") or 65.0)
    consist = nutrition.consistency_score()
    lvl     = gamification.level()

    prot_goal = nutrition.calc_protein_goal(w, user.get("health_mode", "general"))

    # ── MÉTRICAS ──────────────────────────────────────────────────────────
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

    # ── BARRAS DE PROGRESSO ───────────────────────────────────────────────
    tmb  = nutrition.calc_tmb(w, user.get("height"), user.get("age"),
                               user.get("gender", "female"))
    meta = nutrition.calc_goal_calories(
        tmb, user.get("activity_level", "moderate"),
        user.get("goal", "lose"), user.get("health_mode", "general"),
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

    # ── GRÁFICOS ──────────────────────────────────────────────────────────
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**📈 Calorias — Últimos 7 Dias**")
        wk = nutrition.weekly_summary()
        if not wk.empty:
            calories_area_chart(wk, meta)
        else:
            empty_state("📊", "Sem dados", "Registre por 2+ dias")

    with c2:
        st.markdown("**🥗 Macros de Hoje**")
        if sm["calories"] > 0:
            macros_pie_chart(sm["protein"], sm["carbs"], sm["fat"])
        else:
            empty_state("🥗", "Sem refeições hoje")

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🥩 Proteína — Últimos 7 Dias**")
        wk2 = nutrition.weekly_summary()
        if not wk2.empty and "protein" in wk2.columns:
            protein_week_chart(wk2, prot_goal)
        else:
            empty_state("🥩", "Sem dados de proteína")

    with c2:
        st.markdown("**⚖️ Evolução de Peso**")
        df_w = db.get_weights(90)
        if not df_w.empty and len(df_w) >= 2:
            weight_line_chart(df_w, g_w)
        else:
            empty_state("⚖️", "Registre seu peso para ver o gráfico")

    # ── PERÍODO ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**🕐 Calorias por Período (30 dias)**")
    pd_data = nutrition.period_analysis()
    if any(v > 0 for v in pd_data["calories_by_period"].values()):
        period_bar_chart(pd_data["calories_by_period"])
    else:
        empty_state("🕐", "Sem dados de período")

    # ── EXPORTAÇÃO ────────────────────────────────────────────────────────
    st.markdown("---")
    if plan_svc.can_use(user, "export"):
        st.markdown("**💾 Exportar Dados**")
        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            st.download_button(
                "📥 Refeições CSV",
                db.export_meals_csv(),
                f"melshape_refeicoes_{date.today()}.csv",
                "text/csv",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "📥 Peso CSV",
                db.export_weights_csv(),
                f"melshape_peso_{date.today()}.csv",
                "text/csv",
                use_container_width=True,
            )
    else:
        st.caption("💾 Exportação disponível no plano Pro.")

    medical_disclaimer()
    st.markdown('</div>', unsafe_allow_html=True)
