"""Melshape — Registro de suplementos com sugestões por modo de saúde."""
import streamlit as st
from datetime import date, datetime
from core.models import Supplement
from core.models.supplement import BARIATRIC_ESSENTIALS, GLP1_COMMON
from views.components import empty_state, section_header, alert, medical_disclaimer


def render(services: dict, user: dict) -> None:
    db       = services["db"]
    plan_svc = services["plan"]

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    section_header("💊 Suplementação", "Vitaminas, minerais e proteínas")

    if not plan_svc.can_use(user, "supplements"):
        plan_svc.show_paywall("Registro de Suplementos", user)
        medical_disclaimer()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    mode = user.get("health_mode", "general")

    if mode == "bariatric":
        alert(
            "🔪 <b>Suplementação bariátrica é essencial.</b> Deficiências de B12, D3, "
            "ferro e cálcio são comuns no pós-operatório. Consulte seu nutricionista.",
            "bariatric",
        )
        suggestions = BARIATRIC_ESSENTIALS
    elif mode == "glp1":
        alert(
            "💉 <b>GLP-1 e proteína:</b> com menos apetite, suplementar proteína é "
            "fundamental para preservar massa muscular.",
            "glp1",
        )
        suggestions = GLP1_COMMON
    else:
        suggestions = []

    tab_add, tab_today, tab_suggest = st.tabs(
        ["➕ Registrar", "📋 Hoje", "💡 Sugestões"]
    )

    with tab_add:
        with st.form("supl_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name     = st.text_input("Nome do suplemento")
                dose     = st.text_input("Dose", placeholder="Ex: 30")
                unit     = st.selectbox(
                    "Unidade",
                    ["g", "mg", "mcg", "UI", "ml", "cápsula", "comprimido"],
                )
            with c2:
                category = st.selectbox(
                    "Categoria",
                    ["protein", "vitamin", "mineral", "medication", "other"],
                    format_func=lambda x: {
                        "protein":    "🥩 Proteína",
                        "vitamin":    "🌟 Vitamina",
                        "mineral":    "⛏️ Mineral",
                        "medication": "💊 Medicamento",
                        "other":      "📦 Outro",
                    }[x],
                )
                time_taken = st.time_input("Horário", value=datetime.now().time())
                notes      = st.text_input("Observações (opcional)")

            if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                if name.strip():
                    s = Supplement(
                        name=name.strip(), dose=dose, unit=unit,
                        category=category, time_taken=time_taken.strftime("%H:%M"),
                        notes=notes, log_date=date.today().isoformat(),
                    )
                    db.save_supplement(s)
                    st.success(f"✅ {name} registrado!")
                    st.rerun()
                else:
                    st.error("Informe o nome do suplemento.")

    with tab_today:
        supls = db.get_supplements_today()
        if supls:
            total_prot = sum(
                float(s.dose or 0) for s in supls
                if s.category == "protein" and s.unit == "g"
            )
            if total_prot > 0:
                st.info(f"🥩 Proteína via suplemento hoje: **{total_prot:.0f}g**")
            for s in supls:
                st.markdown(
                    f'<div class="supl-item">'
                    f'<span><b>{s.name}</b> · {s.dose} {s.unit}</span>'
                    f'<span style="color:#C9A84C;">{s.time_taken}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            empty_state("💊", "Nenhum suplemento hoje", "Registre agora!")

    with tab_suggest:
        if suggestions:
            st.markdown("**Recomendados para seu perfil:**")
            for s in suggestions:
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(
                        f'<div class="supl-item">'
                        f'<span><b>{s["name"]}</b> · {s["dose"]} {s["unit"]}</span>'
                        f'<span style="color:#64748b;">{s["category"]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with c2:
                    if st.button("+ Add", key=f"add_{s['name']}", use_container_width=True):
                        supl = Supplement(
                            name=s["name"], dose=s["dose"], unit=s["unit"],
                            category=s["category"],
                            time_taken=datetime.now().strftime("%H:%M"),
                            log_date=date.today().isoformat(),
                        )
                        db.save_supplement(supl)
                        st.success(f"✅ {s['name']} adicionado!")
                        st.rerun()
        else:
            st.info("Complete o perfil de saúde para ver sugestões personalizadas.")

    medical_disclaimer()
    st.markdown('</div>', unsafe_allow_html=True)
