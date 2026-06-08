"""Melshape — Perfil do paciente com planos, GLP-1, bariátrico e LGPD."""
import streamlit as st
import config
from views.components import section_header, medical_disclaimer


def render(services: dict, user: dict) -> None:
    db        = services["db"]
    nutrition = services["nutrition"]

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    section_header("👤 Meu Perfil", "Dados pessoais, modo de saúde e planos")

    tab_dados, tab_saude, tab_plano = st.tabs(
        ["📋 Dados Pessoais", "🏥 Modo de Saúde", "💳 Plano & Privacidade"]
    )

    # ── DADOS PESSOAIS ────────────────────────────────────────────────────
    with tab_dados:
        with st.form("profile_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                nome    = st.text_input("Nome completo", user.get("name", ""))
                st.text_input("Email", user.get("email", ""), disabled=True)
                gender  = st.selectbox(
                    "Gênero",
                    ["female", "male", "other"],
                    index=["female","male","other"].index(user.get("gender","female")),
                    format_func=lambda x: {"female":"Feminino","male":"Masculino","other":"Outro"}[x],
                )
                idade   = st.number_input("Idade", 12, 110, int(user.get("age") or 30), 1)
                altura  = st.number_input("Altura (cm)", 100, 250, int(user.get("height") or 165), 1)
            with c2:
                peso    = st.number_input("Peso atual (kg)", 30.0, 300.0,
                                          float(user.get("current_weight") or 70.0), 0.1)
                meta_p  = st.number_input("Peso meta (kg)", 30.0, 300.0,
                                          float(user.get("goal_weight") or 65.0), 0.1)
                objetivo = st.selectbox(
                    "Objetivo",
                    ["lose","maintain","gain"],
                    index=["lose","maintain","gain"].index(user.get("goal","lose")),
                    format_func=lambda x: {
                        "lose":"⬇️ Emagrecer",
                        "maintain":"↔️ Manter peso",
                        "gain":"⬆️ Ganhar massa",
                    }[x],
                )
                ativ = st.selectbox(
                    "Nível de atividade",
                    list(config.ACTIVITY_FACTORS.keys()),
                    index=list(config.ACTIVITY_FACTORS.keys()).index(
                        user.get("activity_level","moderate")
                    ),
                    format_func=lambda x: config.ACTIVITY_LABELS[x],
                )

            # Preview de cálculos
            if all([peso, altura, idade]):
                tmb    = nutrition.calc_tmb(peso, altura, idade, gender)
                tdee   = nutrition.calc_tdee(tmb, ativ)
                meta   = nutrition.calc_goal_calories(
                    tmb, ativ, objetivo, user.get("health_mode","general")
                )
                prot   = nutrition.calc_protein_goal(peso, user.get("health_mode","general"))
                macros = nutrition.calc_macros_goal(meta, objetivo)

                st.markdown("**🧮 Seus cálculos**")
                c1b, c2b, c3b, c4b = st.columns(4)
                with c1b: st.metric("TMB",      f"{tmb} kcal")
                with c2b: st.metric("TDEE",     f"{tdee} kcal")
                with c3b: st.metric("Meta",     f"{meta} kcal/dia")
                with c4b: st.metric("Proteína", f"{prot:.0f}g/dia")
                st.markdown(
                    f'<div style="background:rgba(201,168,76,.08);border-radius:8px;'
                    f'padding:0.55rem 0.9rem;font-size:0.8rem;color:#78350f;">'
                    f'Macros: 🥩 P {macros["protein"]}g · '
                    f'🍚 C {macros["carbs"]}g · '
                    f'🧈 G {macros["fat"]}g'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if st.form_submit_button("💾 Salvar Dados", type="primary", use_container_width=True):
                updates = {
                    "name": nome, "gender": gender,
                    "age": idade, "height": altura,
                    "current_weight": peso, "goal_weight": meta_p,
                    "goal": objetivo, "activity_level": ativ,
                }
                user.update(updates)
                db.update_user(updates)
                st.session_state.user = user
                st.success("✅ Dados salvos!")
                st.rerun()

    # ── MODO DE SAÚDE ─────────────────────────────────────────────────────
    with tab_saude:
        mode = user.get("health_mode","general")
        mode_labels = {
            "general":   "⚖️ Emagrecimento",
            "bariatric": "🔪 Pós-Bariátrica",
            "glp1":      "💉 GLP-1 / Canetas",
            "fitness":   "💪 Fitness",
        }
        st.markdown("**Modo atual:**")
        st.markdown(
            f'<span class="mode-badge mode-{mode}">{mode_labels.get(mode,"Geral")}</span>',
            unsafe_allow_html=True,
        )
        st.markdown("")

        new_mode = st.selectbox(
            "Alterar modo",
            list(mode_labels.keys()),
            index=list(mode_labels.keys()).index(mode),
            format_func=lambda x: mode_labels[x],
        )

        extra: dict = {}
        if new_mode == "glp1":
            st.markdown("##### 💉 GLP-1")
            med   = st.selectbox("Medicamento", config.GLP1_MEDICATIONS,
                                 index=(config.GLP1_MEDICATIONS.index(user.get("glp1_medication","Outro"))
                                        if user.get("glp1_medication") in config.GLP1_MEDICATIONS else 0))
            doses = config.GLP1_DOSES.get(med, ["Personalizado"])
            dose  = st.selectbox("Dose", doses)
            phase = st.selectbox(
                "Fase",
                list(config.GLP1_PHASES.keys()),
                format_func=lambda x: config.GLP1_PHASES[x],
            )
            extra = {"uses_glp1": True, "glp1_medication": med,
                     "glp1_dose": dose, "glp1_phase": phase}

        elif new_mode == "bariatric":
            st.markdown("##### 🔪 Bariátrica")
            btype = st.selectbox(
                "Tipo de cirurgia",
                list(config.BARIATRIC_TYPES.keys()),
                format_func=lambda x: config.BARIATRIC_TYPES[x],
            )
            phase = st.selectbox(
                "Fase atual",
                list(config.BARIATRIC_PHASES.keys()),
                format_func=lambda x: config.BARIATRIC_PHASES[x]["name"],
            )
            extra = {"is_bariatric": True, "bariatric_type": btype,
                     "bariatric_phase": phase}

        if st.button("💾 Salvar Modo", type="primary", use_container_width=True):
            updates = {"health_mode": new_mode, **extra}
            user.update(updates)
            db.update_user(updates)
            st.session_state.user = user
            st.success("✅ Modo atualizado!")
            st.rerun()

    # ── PLANO & PRIVACIDADE ───────────────────────────────────────────────
    with tab_plano:
        from core.models import User as UserModel
        u_obj    = UserModel.from_dict(user)
        eff_plan = u_obj.effective_plan()
        days_rem = u_obj.trial_days_remaining()

        plan_labels = {
            "free":     "🆓 FREE",
            "trial":    f"⏳ TRIAL ({days_rem}d restantes)",
            "essencial":"💎 ESSENCIAL",
            "pro":      "⭐ PRO",
            "lifetime": "👑 VITALÍCIO",
        }
        plan_colors = {
            "free":"#64748b","trial":"#C9A84C",
            "essencial":"#3D5A73","pro":"#C9A84C","lifetime":"#1C1C1E",
        }
        pc = plan_colors.get(eff_plan,"#64748b")
        pl = plan_labels.get(eff_plan,"FREE")

        st.markdown(
            f'<div style="background:{pc}12;border:2px solid {pc}35;border-radius:16px;'
            f'padding:1.35rem;text-align:center;margin-bottom:1.35rem;">'
            f'<div style="font-family:Sora,sans-serif;font-size:1.7rem;font-weight:800;color:{pc};">'
            f'{pl}</div>'
            f'<div style="color:#64748b;font-size:0.85rem;">Plano atual</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if eff_plan in ("free","trial"):
            st.markdown("### 🚀 Fazer Upgrade")
            c1, c2, c3 = st.columns(3)
            plans_info = [
                ("essencial","💎 ESSENCIAL",
                 f"R${config.PATIENT_PRICES['essencial']['monthly']:.2f}/mês",
                 "Ilimitado · 90d histórico · GLP-1 · Suplementos · Hidratação",
                 "#3D5A73"),
                ("pro","⭐ PRO",
                 f"R${config.PATIENT_PRICES['pro']['monthly']:.2f}/mês",
                 "Tudo + Bariátrico · Treino · Sono · Exportação",
                 "#C9A84C"),
                ("lifetime","👑 VITALÍCIO",
                 f"R${config.PATIENT_PRICES['lifetime']['once']:.0f} único",
                 "Tudo para sempre · Sem mensalidade · Updates futuros",
                 "#1C1C1E"),
            ]
            for col, (plan_key, title, price, features, color) in zip([c1,c2,c3], plans_info):
                with col:
                    st.markdown(
                        f'<div style="background:{color}0e;border:1px solid {color}35;'
                        f'border-radius:14px;padding:1.1rem;text-align:center;height:185px;">'
                        f'<div style="font-family:Sora,sans-serif;font-weight:700;color:{color};">'
                        f'{title}</div>'
                        f'<div style="font-size:1.45rem;font-weight:800;color:{color};margin:0.35rem 0;">'
                        f'{price}</div>'
                        f'<div style="font-size:0.75rem;color:#64748b;">{features}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("")
                    if st.button(
                        f"Assinar {title.split()[1]}",
                        use_container_width=True,
                        key=f"plan_{plan_key}",
                        type="primary" if plan_key == "pro" else "secondary",
                    ):
                        user["plan"] = plan_key
                        db.update_user({"plan": plan_key})
                        st.session_state.user = user
                        st.success(f"✅ Plano {title} ativado!")
                        st.rerun()
        else:
            st.success(f"✅ Você tem acesso **{pl}**. Aproveite todos os recursos!")

        # LGPD e exclusão de dados
        st.markdown("---")
        st.markdown("**🔒 Privacidade & LGPD**")
        lgpd_ts = user.get("lgpd_accepted_at","")
        if lgpd_ts:
            st.markdown(f"✅ Termos aceitos em: `{lgpd_ts[:10]}`")

        col_exp, col_del = st.columns(2)
        with col_exp:
            csv = db.export_meals_csv()
            st.download_button(
                "📥 Exportar meus dados",
                csv,
                "melshape_meus_dados.csv",
                "text/csv",
                use_container_width=True,
                help="Exporta refeições conforme direito de portabilidade (LGPD art. 18)",
            )
        with col_del:
            if st.button("🗑️ Excluir minha conta", use_container_width=True, type="secondary"):
                st.session_state["confirm_delete"] = True

        if st.session_state.get("confirm_delete"):
            st.warning("⚠️ Esta ação é irreversível. Todos os seus dados serão apagados.")
            col_y, col_n = st.columns(2)
            with col_y:
                if st.button("✅ Confirmar exclusão", use_container_width=True, type="primary"):
                    uid = user.get("email","")
                    for key in ("meals","weights","supplements","workouts",
                                "achievements","hydration","symptoms","sleep","cycles"):
                        st.session_state.mock_db[key] = [
                            x for x in st.session_state.mock_db.get(key,[])
                            if x.get("user_id") != uid
                        ]
                    st.session_state.mock_db["users"].pop(uid, None)
                    for k in ("user","demo_loaded","confirm_delete"):
                        st.session_state.pop(k, None)
                    st.session_state.page = "landing"
                    st.success("🗑️ Conta excluída.")
                    st.rerun()
            with col_n:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.session_state.pop("confirm_delete", None)
                    st.rerun()

    medical_disclaimer()
    st.markdown('</div>', unsafe_allow_html=True)
