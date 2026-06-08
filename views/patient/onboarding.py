"""Melshape — Onboarding de 3 passos (corrigido: sem services=None)."""
import streamlit as st
from datetime import date
import config


def render(services: dict, user: dict) -> None:
    db   = services["db"]
    step = st.session_state.get("onboarding_step", 1)

    st.markdown(
        '<div class="hero-banner" style="padding:1.65rem 2rem;">'
        '<h1 style="font-size:1.75rem;">🔥 Bem-vindo ao Melshape!</h1>'
        '<p>Configure sua jornada em 3 passos rápidos.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    pct = int((step / 3) * 100)
    st.markdown(
        f'<div style="background:#f1f5f9;border-radius:9999px;height:7px;margin-bottom:1.25rem;">'
        f'<div style="background:linear-gradient(90deg,#C9A84C,#a8862e);height:100%;'
        f'width:{pct}%;border-radius:9999px;"></div>'
        f'</div>'
        f'<div style="text-align:center;font-size:0.82rem;color:#64748b;margin-bottom:1rem;">'
        f'Passo {step} de 3</div>',
        unsafe_allow_html=True,
    )

    if step == 1:
        _step1(db, user)
    elif step == 2:
        _step2(db, user)
    elif step == 3:
        _step3(db, user)


def _step1(db, user: dict) -> None:
    st.markdown("### 👤 Dados pessoais")
    with st.form("onboarding_s1", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            gender = st.selectbox(
                "Gênero",
                ["female", "male", "other"],
                index=["female", "male", "other"].index(user.get("gender", "female")),
                format_func=lambda x: {"female": "Feminino", "male": "Masculino", "other": "Outro"}[x],
            )
            age    = st.number_input("Idade", 12, 110, int(user.get("age") or 30), 1)
            height = st.number_input("Altura (cm)", 100, 250, int(user.get("height") or 165), 1)
        with c2:
            weight = st.number_input("Peso atual (kg)", 30.0, 300.0,
                                     float(user.get("current_weight") or 75.0), 0.1)
            goal_w = st.number_input("Peso meta (kg)", 30.0, 300.0,
                                     float(user.get("goal_weight") or 65.0), 0.1)
            activity = st.selectbox(
                "Nível de atividade",
                list(config.ACTIVITY_FACTORS.keys()),
                index=2,
                format_func=lambda x: config.ACTIVITY_LABELS[x],
            )

        if st.form_submit_button("Próximo →", type="primary", use_container_width=True):
            updates = {
                "gender": gender, "age": age, "height": height,
                "current_weight": weight, "goal_weight": goal_w,
                "activity_level": activity,
            }
            user.update(updates)
            db.update_user(updates)
            st.session_state.user = user
            st.session_state.onboarding_step = 2
            st.rerun()


def _step2(db, user: dict) -> None:
    st.markdown("### 🎯 Sua jornada de saúde")

    modes = {
        "general":   ("⚖️", "Emagrecimento",  "Quero perder peso com consistência e dados reais."),
        "fitness":   ("🏋️", "Fitness",         "Otimizo nutrição pelo meu protocolo de treino."),
        "glp1":      ("💉", "GLP-1 / Canetas", "Uso Ozempic, Mounjaro ou similar."),
        "bariatric": ("🔪", "Pós-Bariátrica",  "Fiz cirurgia bariátrica."),
    }

    selected = st.session_state.get("onboarding_mode", "general")

    c1, c2 = st.columns(2)
    for i, (mode, (icon, title, desc)) in enumerate(modes.items()):
        col = c1 if i % 2 == 0 else c2
        with col:
            kind = "primary" if selected == mode else "secondary"
            if st.button(
                f"{icon} {title}\n{desc}",
                use_container_width=True,
                key=f"mode_{mode}",
                type=kind,
            ):
                st.session_state.onboarding_mode = mode
                st.rerun()

    # Campos específicos por modo
    extra: dict = {}
    mode_key = st.session_state.get("onboarding_mode", "general")

    if mode_key == "glp1":
        st.markdown("##### 💉 Detalhes do GLP-1")
        med   = st.selectbox("Medicamento", config.GLP1_MEDICATIONS)
        doses = config.GLP1_DOSES.get(med, ["Personalizado"])
        dose  = st.selectbox("Dose atual", doses)
        start = st.date_input("Data de início", value=date.today())
        extra = {
            "uses_glp1": True, "glp1_medication": med,
            "glp1_dose": dose, "glp1_start_date": start.isoformat(),
            "glp1_phase": "adapting",
        }
    elif mode_key == "bariatric":
        st.markdown("##### 🔪 Detalhes da cirurgia")
        btype = st.selectbox(
            "Tipo",
            list(config.BARIATRIC_TYPES.keys()),
            format_func=lambda x: config.BARIATRIC_TYPES[x],
        )
        sdate = st.date_input("Data da cirurgia", value=date.today())
        phase = st.selectbox(
            "Fase atual",
            list(config.BARIATRIC_PHASES.keys()),
            format_func=lambda x: config.BARIATRIC_PHASES[x]["name"],
        )
        extra = {
            "is_bariatric": True, "bariatric_type": btype,
            "surgery_date": sdate.isoformat(), "bariatric_phase": phase,
        }

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Voltar", use_container_width=True):
            st.session_state.onboarding_step = 1
            st.rerun()
    with col2:
        if st.button("Próximo →", type="primary", use_container_width=True):
            updates = {"health_mode": mode_key, **extra}
            user.update(updates)
            db.update_user(updates)
            st.session_state.user = user
            st.session_state.onboarding_step = 3
            st.rerun()


def _step3(db, user: dict) -> None:
    st.markdown("### 🎯 Seu objetivo principal")

    goal_opts = {
        "lose":     ("⬇️ Emagrecer",    "Reduzir o peso corporal"),
        "maintain": ("↔️ Manter peso",   "Manter o peso atual"),
        "gain":     ("⬆️ Ganhar massa",  "Ganhar massa muscular"),
    }

    goal = st.radio(
        "Objetivo",
        list(goal_opts.keys()),
        format_func=lambda x: f"{goal_opts[x][0]} — {goal_opts[x][1]}",
        index=0,
    )

    # Preview dos cálculos — sem injetar services, usa config direto
    w   = float(user.get("current_weight") or 75.0)
    h   = int(user.get("height") or 165)
    a   = int(user.get("age") or 30)
    g   = user.get("gender", "female")
    act = user.get("activity_level", "moderate")
    mode= user.get("health_mode", "general")

    base = 10 * w + 6.25 * h - 5 * a
    tmb  = int(base + 5) if g == "male" else int(base - 161)
    tdee = int(tmb * config.ACTIVITY_FACTORS.get(act, 1.55))
    if goal == "lose":
        meta = max(1200, tdee - 500)
    elif goal == "gain":
        meta = tdee + 300
    else:
        meta = tdee
    per_kg = {
        "glp1": config.GLP1_PROTEIN_PER_KG,
        "bariatric": config.BARIATRIC_PROTEIN_PER_KG,
        "fitness": config.FITNESS_PROTEIN_PER_KG,
    }.get(mode, config.GENERAL_PROTEIN_PER_KG)
    prot = round(w * per_kg, 1)

    st.markdown(
        f'<div style="background:rgba(201,168,76,.10);border:1px solid rgba(201,168,76,.35);'
        f'border-radius:12px;padding:0.9rem 1rem;text-align:center;margin:0.75rem 0;">'
        f'<div style="font-size:0.83rem;color:#78350f;">'
        f'TMB: <b>{tmb} kcal</b> · TDEE: <b>{tdee} kcal</b> · '
        f'Meta: <b>{meta} kcal/dia</b> · Proteína: <b>{prot:.0f}g/dia</b>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Voltar", use_container_width=True):
            st.session_state.onboarding_step = 2
            st.rerun()
    with col2:
        if st.button("🚀 Começar Agora!", type="primary", use_container_width=True):
            updates = {"goal": goal, "onboarding_done": True}
            user.update(updates)
            db.update_user(updates)
            st.session_state.user = user
            st.session_state.onboarding_step = 1
            st.session_state.page = "home"
            st.rerun()
