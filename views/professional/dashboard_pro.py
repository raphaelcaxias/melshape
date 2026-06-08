"""Melshape — Painel do profissional de saúde com triagem clínica."""
import streamlit as st
from views.components import section_header, empty_state, metric_card, alert
import config


def render(services: dict, professional: dict) -> None:
    pro_svc = services["professional"]
    db      = services["db"]

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    section_header(
        f"🏥 Painel — {professional.get('name','')}",
        professional.get("specialty",""),
    )

    col_menu, col_content = st.columns([1, 4])

    with col_menu:
        st.markdown("**Menu**")
        pages = [
            ("👥", "Pacientes",  "pro_patients"),
            ("📊", "Relatórios", "pro_reports"),
            ("👤", "Perfil",     "pro_profile"),
        ]
        for icon, label, key in pages:
            cur  = st.session_state.get("pro_page","pro_patients")
            kind = "primary" if cur == key else "secondary"
            if st.button(f"{icon} {label}", use_container_width=True,
                         type=kind, key=f"pro_nav_{key}"):
                st.session_state.pro_page = key
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True):
            for k in ("professional","pro_page","pro_selected_patient"):
                st.session_state.pop(k, None)
            st.session_state.page = "landing"
            st.rerun()

    with col_content:
        pro_page = st.session_state.get("pro_page","pro_patients")
        if pro_page == "pro_patients":
            _patients_view(db, pro_svc, professional)
        elif pro_page == "pro_reports":
            _reports_view(db, pro_svc, professional)
        elif pro_page == "pro_profile":
            _profile_view(professional)

    st.markdown('</div>', unsafe_allow_html=True)


def _patients_view(db, pro_svc, professional: dict) -> None:
    email    = professional.get("email","")
    patients = pro_svc.get_patients(email)

    # Triagem
    triage   = pro_svc.get_triage_list(patients)
    critical = triage["critical"]
    warning  = triage["warning"]
    ok_list  = triage["ok"]

    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card(str(len(patients)), "Total Pacientes", "👥")
    with c2: metric_card(str(len(critical)), "🚨 Críticos",     "🚨", "red" if critical else "green")
    with c3: metric_card(str(len(warning)),  "⚠️ Atenção",      "⚠️", "amber" if warning else "green")
    with c4: metric_card(str(len(ok_list)),  "✅ Em Dia",        "✅", "green")

    # Código de convite
    code = email.split("@")[0].upper()
    st.markdown(
        f'<div class="alert-info">🔗 <b>Código de convite:</b> '
        f'<code style="background:#e0f0ff;padding:0.15rem 0.4rem;border-radius:4px;">{code}</code>'
        f' — Pacientes usam esse código ao se cadastrar.</div>',
        unsafe_allow_html=True,
    )

    # Busca
    search_term = st.text_input("🔍 Buscar paciente por nome ou email")

    # Filtro
    all_enriched = critical + warning + ok_list
    if search_term:
        term = search_term.lower()
        all_enriched = [
            p for p in all_enriched
            if term in p.get("name","").lower() or term in p.get("email","").lower()
        ]

    if not all_enriched:
        empty_state("👥", "Nenhum paciente encontrado",
                    "Compartilhe seu código para pacientes se conectarem.")
        return

    # Seções de triagem
    for section_label, section_list, css_class, icon in [
        ("🚨 Críticos — Ação imediata",    critical, "patient-critical", "🚨"),
        ("⚠️ Atenção — Verificar hoje",     warning,  "patient-warning",  "⚠️"),
        ("✅ Em Dia",                        ok_list,  "patient-ok",       "✅"),
    ]:
        if not section_list:
            continue
        st.markdown(f"**{section_label}** ({len(section_list)})")
        for p in section_list:
            summary = p.get("summary", {})
            reasons = p.get("triage_reasons", [])
            mode_icon = {"general":"⚖️","bariatric":"🔪","glp1":"💉","fitness":"💪"}.get(
                p.get("health_mode","general"),"⚖️"
            )
            reasons_html = (
                "<br>".join(f'<span style="font-size:0.75rem;color:#b91c1c;">⚠ {r}</span>'
                             for r in reasons)
                if reasons else ""
            )
            st.markdown(
                f'<div class="patient-card {css_class}">'
                f'<b>{mode_icon} {p.get("name","")}</b> · {p.get("email","")}'
                f'<br><span style="font-size:0.8rem;color:#64748b;">'
                f'Hoje: 🔥 {summary.get("cal_today",0)} kcal · '
                f'🥩 {summary.get("prot_today",0):.0f}g prot · '
                f'📅 {summary.get("days_logged",0)} dias registrados'
                f'</span><br>{reasons_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button(
                f"Ver detalhes — {p.get('name','')}",
                key=f"detail_{p.get('email','')}",
            ):
                st.session_state.pro_selected_patient = p.get("email","")
                st.session_state.pro_page = "pro_patient_detail"
                st.rerun()
        st.markdown("")


def _reports_view(db, pro_svc, professional: dict) -> None:
    st.markdown("**📊 Relatórios**")
    email    = professional.get("email","")
    patients = pro_svc.get_patients(email)

    if not patients:
        empty_state("📊","Sem pacientes","Vincule pacientes para gerar relatórios.")
        return

    st.info("📋 Exportação em PDF disponível no plano Clínica e superior.")

    # Tabela de resumo usando st.dataframe
    import pandas as pd
    rows = []
    for p in patients:
        s = pro_svc.get_patient_summary(p.get("email",""))
        rows.append({
            "Nome":         p.get("name",""),
            "Modo":         p.get("health_mode","general"),
            "Cal. hoje":    s.get("cal_today",0),
            "Prot. hoje":   f'{s.get("prot_today",0):.0f}g',
            "Peso atual":   f'{s.get("last_weight") or "—"} kg',
            "Variação":     f'{s.get("weight_diff") or "—"} kg',
            "Dias registr.":s.get("days_logged",0),
            "Gap (dias)":   s.get("gap_days",0),
        })
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    # Download
    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Exportar resumo CSV",
        csv,
        f"melshape_pacientes_{professional.get('email','')}.csv",
        "text/csv",
        use_container_width=False,
    )


def _profile_view(professional: dict) -> None:
    st.markdown("**👤 Perfil Profissional**")
    spec_labels = {
        "nutritionist":    "🥗 Nutricionista",
        "endocrinologist": "🩺 Endocrinologista",
        "other":           "👨‍⚕️ Outro",
    }
    st.markdown(f"**Nome:** {professional.get('name','')}")
    st.markdown(f"**Especialidade:** {spec_labels.get(professional.get('specialty',''),'')}")
    st.markdown(f"**Registro:** {professional.get('crn_number','')}")
    st.markdown(f"**Plano:** {professional.get('pro_plan','starter').upper()}")

    st.markdown("---")
    st.markdown("**💳 Planos Profissionais**")
    for plan_key, info in config.PRO_PLAN_LIMITS.items():
        is_current = plan_key == professional.get("pro_plan","starter")
        border = "#C9A84C" if is_current else "#e8e0d0"
        st.markdown(
            f'<div style="background:{"rgba(201,168,76,.08)" if is_current else "#f8fafc"};'
            f'border:1px solid {border};border-radius:10px;'
            f'padding:0.7rem 1rem;margin-bottom:0.35rem;display:flex;justify-content:space-between;">'
            f'<span><b>{plan_key.upper()}</b> · Até {info["patients"]} pacientes'
            f'{"  ← atual" if is_current else ""}</span>'
            f'<span style="color:#C9A84C;font-weight:700;">R${info["price"]:.2f}/mês</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
