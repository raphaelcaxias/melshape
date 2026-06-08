"""Melshape — Detalhe clínico de um paciente (painel profissional)."""
import streamlit as st
from views.components import section_header, empty_state, metric_card, alert


def render(services: dict, professional: dict) -> None:
    db      = services["db"]
    pro_svc = services["professional"]

    patient_email = st.session_state.get("pro_selected_patient","")
    if not patient_email:
        st.warning("Nenhum paciente selecionado.")
        return

    # Busca dados do paciente
    patients = pro_svc.get_patients(professional.get("email",""))
    patient  = next((p for p in patients if p.get("email") == patient_email), None)
    if not patient:
        st.warning("Paciente não encontrado.")
        return

    if st.button("← Voltar à lista", type="secondary"):
        st.session_state.pro_page = "pro_patients"
        st.session_state.pop("pro_selected_patient", None)
        st.rerun()

    mode_labels = {
        "general":"⚖️ Emagrecimento","bariatric":"🔪 Pós-Bariátrica",
        "glp1":"💉 GLP-1","fitness":"💪 Fitness",
    }
    mode = patient.get("health_mode","general")

    # Header clínico
    st.markdown(
        f'<div class="hero-banner" style="padding:1.5rem 2rem;">'
        f'<h2 style="margin:0;font-size:1.6rem;">'
        f'👤 {patient.get("name","")} — {mode_labels.get(mode,"")}'
        f'</h2>'
        f'<p style="margin:0.3rem 0 0;opacity:0.9;">{patient_email}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Insights
    insights = pro_svc.get_patient_insights(patient_email)
    summary  = insights["summary"]

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card(f'{summary.get("cal_today",0)} kcal', "Calorias hoje", "🔥")
    with c2: metric_card(f'{summary.get("prot_today",0):.0f}g', "Proteínas hoje", "🥩", "green")
    with c3: metric_card(f'{summary.get("last_weight") or "—"} kg', "Último peso", "⚖️","steel")
    with c4: metric_card(f'{summary.get("days_logged",0)}', "Dias registrados", "📅","carbon")

    # Tendência
    trend = insights["weight_trend"]
    st.markdown(f"**📊 Tendência de peso:** {trend}")
    st.markdown(f"**⏳ Dias sem registro:** {summary.get('gap_days',0)}")

    if summary.get("gap_days",0) >= 3:
        alert(
            f"⚠️ Paciente sem registro há {summary.get('gap_days',0)} dias. "
            "Considere entrar em contato.",
            "warning",
        )

    # Refeições recentes
    st.markdown("---")
    st.markdown("**🍽️ Últimas Refeições**")
    meals_all = [m for m in db._mock().get("meals",[]) if m.get("user_id") == patient_email]
    meals_all = sorted(meals_all, key=lambda x: (x.get("meal_date",""), x.get("meal_time","")), reverse=True)[:10]
    if meals_all:
        import pandas as pd
        df_meals = pd.DataFrame(meals_all)[["meal_date","meal_time","food","calories","protein","carbs","fat"]]
        df_meals.columns = ["Data","Horário","Alimento","Kcal","Prot (g)","Carbs (g)","Gord (g)"]
        st.dataframe(df_meals, use_container_width=True, hide_index=True)
    else:
        empty_state("🍽️","Sem refeições registradas")

    # Suplementos
    st.markdown("**💊 Suplementos Recentes**")
    supls = [s for s in db._mock().get("supplements",[]) if s.get("user_id") == patient_email]
    if supls:
        for s in supls[-5:]:
            st.markdown(
                f'<div class="supl-item">'
                f'<span><b>{s.get("name")}</b> · {s.get("dose")} {s.get("unit")}</span>'
                f'<span style="color:#C9A84C;">{s.get("log_date")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("Nenhum suplemento registrado.")

    # Peso histórico
    st.markdown("**⚖️ Histórico de Peso**")
    weights = [w for w in db._mock().get("weights",[]) if w.get("user_id") == patient_email]
    if len(weights) >= 2:
        import pandas as pd
        from views.components import weight_line_chart
        df_w = pd.DataFrame(weights)
        df_w["log_date"] = pd.to_datetime(df_w["log_date"])
        df_w = df_w.sort_values("log_date")
        weight_line_chart(df_w, float(patient.get("goal_weight") or 0) or None)
    else:
        empty_state("⚖️","Poucas pesagens","Paciente precisa registrar mais pesagens.")

    # Exportar dados do paciente
    st.markdown("---")
    st.markdown("**💾 Exportar Dados do Paciente**")
    if meals_all:
        import pandas as pd
        df_exp = pd.DataFrame(meals_all)
        csv = df_exp.to_csv(index=False)
        st.download_button(
            "📥 Exportar refeições CSV",
            csv,
            f"melshape_{patient.get('name','paciente').replace(' ','_')}_refeicoes.csv",
            "text/csv",
        )
