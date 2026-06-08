"""Melshape — Análises, conquistas e desafios."""
import streamlit as st
from datetime import date
from views.components import (
    achievement_card, challenge_card, empty_state,
    section_header, metric_card, progress_bar,
    period_bar_chart, medical_disclaimer,
)


def render(services: dict, user: dict) -> None:
    db           = services["db"]
    nutrition    = services["nutrition"]
    gamification = services["gamification"]

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    section_header("📈 Análises & Conquistas", "Progresso, padrões e recompensas")

    tab_analysis, tab_achievements, tab_challenges = st.tabs(
        ["📊 Análises", "🏆 Conquistas", "🎯 Desafios"]
    )

    with tab_analysis:
        col_sum, col_consist = st.columns(2)

        with col_sum:
            st.markdown("**📋 Resumo — 30 Dias**")
            meals = db.get_meals(30)
            if meals:
                total_cal   = sum(m.calories for m in meals)
                total_prot  = sum(m.protein  for m in meals)
                days_active = len(set(m.meal_date for m in meals))
                avg_cal     = int(total_cal / days_active) if days_active else 0
                c1, c2 = st.columns(2)
                with c1:
                    metric_card(str(len(meals)),   "Refeições",     "🍴")
                    metric_card(str(days_active),  "Dias ativos",   "📅", "steel")
                with c2:
                    metric_card(f"{avg_cal} kcal", "Média diária",  "🔥", "carbon")
                    metric_card(f"{total_prot:.0f}g","Proteína total","🥩","green")
            else:
                empty_state("📊", "Sem dados", "Registre por 3+ dias")

        with col_consist:
            st.markdown("**✅ Consistência**")
            consist = nutrition.consistency_score()
            streak  = gamification.streak()
            lvl     = gamification.level()
            st.markdown(
                f'<div style="background:white;border-radius:14px;padding:1.4rem;'
                f'border:1px solid #e8e0d0;text-align:center;">'
                f'<div style="font-family:Sora,sans-serif;font-size:2.8rem;'
                f'font-weight:800;color:#C9A84C;">{consist}%</div>'
                f'<div style="font-size:0.8rem;color:#64748b;">dias registrados (30d)</div>'
                f'<hr style="margin:0.65rem 0;border-color:#f1f5f9;">'
                f'<div style="font-size:1.4rem;font-weight:700;color:#3D5A73;">'
                f'📅 {streak} dias</div>'
                f'<div style="font-size:0.8rem;color:#64748b;">sequência atual</div>'
                f'<hr style="margin:0.65rem 0;border-color:#f1f5f9;">'
                f'<div style="font-size:1.05rem;font-weight:700;color:#1C1C1E;">'
                f'{lvl["current"]["icon"]} {lvl["current"]["name"]}</div>'
                f'<div style="font-size:0.75rem;color:#64748b;">'
                f'Nível {lvl["current"]["level"]} · {lvl["xp"]} XP</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Humor
        st.markdown("---")
        st.markdown("**😊 Humor nas Refeições (30 dias)**")
        moods = nutrition.mood_analysis()
        mood_labels = {
            "great": "😄 Ótimo", "good": "🙂 Bom",
            "neutral": "😐 Neutro", "bad": "😕 Ruim", "terrible": "😖 Péssimo",
        }
        total_moods = sum(moods.values())
        if total_moods > 0:
            for key, label in mood_labels.items():
                count = moods.get(key, 0)
                if count > 0:
                    pct = int(count / total_moods * 100)
                    st.markdown(f"{label}: **{count}** registros")
                    progress_bar(count, total_moods, "", f"{pct}%")
        else:
            st.info("Registre o humor nas refeições para ver a análise.")

        # Período
        st.markdown("---")
        st.markdown("**🕐 Calorias por Período (30 dias)**")
        pd_data = nutrition.period_analysis()
        if any(v > 0 for v in pd_data["calories_by_period"].values()):
            period_bar_chart(pd_data["calories_by_period"])
        else:
            empty_state("🕐", "Sem dados", "Continue registrando!")

        # Sugestões
        suggestions = nutrition.suggest_foods()
        if suggestions:
            st.markdown("---")
            st.markdown("**💡 Seus alimentos mais frequentes**")
            cols = st.columns(min(5, len(suggestions)))
            for i, food in enumerate(suggestions):
                with cols[i]:
                    st.markdown(
                        f'<div style="background:rgba(201,168,76,.08);border-radius:10px;'
                        f'padding:0.65rem;text-align:center;border:1px solid rgba(201,168,76,.3);'
                        f'font-size:0.8rem;font-weight:600;color:#78350f;">🍽️ {food}</div>',
                        unsafe_allow_html=True,
                    )

    with tab_achievements:
        achs = db.get_achievements()
        if achs:
            st.success(f"🏆 **{len(achs)}** conquista(s) desbloqueada(s)!")
            cols = st.columns(min(3, len(achs)))
            for i, a in enumerate(achs):
                with cols[i % 3]:
                    achievement_card(a.get("title", ""), a.get("unlocked_at", ""))
        else:
            empty_state("🏆", "Nenhuma conquista ainda", "Registre a primeira refeição!")

        # Bloqueadas
        from services.gamification_service import ACHIEVEMENTS
        earned = {a.get("achievement_name") for a in achs}
        locked = [a for a in ACHIEVEMENTS if a["name"] not in earned]
        if locked:
            st.markdown("---")
            st.markdown("**🔒 Conquistas disponíveis**")
            for ach in locked:
                st.markdown(
                    f'<div style="background:#f8fafc;border:1px solid #e8e0d0;'
                    f'border-radius:12px;padding:0.8rem 1rem;margin-bottom:0.45rem;'
                    f'display:flex;justify-content:space-between;align-items:center;">'
                    f'<div><b>🔒 {ach["title"]}</b><br>'
                    f'<span style="font-size:0.76rem;color:#94a3b8;">{ach["desc"]}</span></div>'
                    f'<span class="xp-badge">+{ach["xp"]} XP</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with tab_challenges:
        wk_num = date.today().isocalendar()[1]
        st.markdown(f"**🗓️ Desafios — Semana {wk_num}/{date.today().year}**")
        challenges = gamification.weekly_challenges()
        for ch in challenges:
            challenge_card(ch["emoji"], ch["title"], ch["xp"])

        st.info("💡 Desafios renovam toda segunda-feira.")

        # Nível
        lvl = gamification.level()
        st.markdown("**🎮 Progresso de Nível**")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#1C1C1E,#3D5A73);'
                f'color:white;border-radius:14px;padding:1.4rem;text-align:center;">'
                f'<div style="font-size:2.2rem;">{lvl["current"]["icon"]}</div>'
                f'<div style="font-family:Sora,sans-serif;font-weight:700;">'
                f'Nível {lvl["current"]["level"]}</div>'
                f'<div style="font-size:0.82rem;opacity:0.8;">{lvl["current"]["name"]}</div>'
                f'<div style="font-size:1.2rem;font-weight:700;margin-top:0.4rem;">'
                f'{lvl["xp"]} XP</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with c2:
            if lvl["next"]:
                st.markdown(f"**Próximo:** {lvl['next']['icon']} {lvl['next']['name']}")
                st.markdown(f"Faltam **{lvl['next']['min_xp'] - lvl['xp']} XP**")
                progress_bar(
                    lvl["xp"] - lvl["current"]["min_xp"],
                    lvl["next"]["min_xp"] - lvl["current"]["min_xp"],
                    f"{lvl['xp']} XP", f"{lvl['next']['min_xp']} XP",
                )
            else:
                st.success("🎉 Nível máximo atingido!")

    medical_disclaimer()
    st.markdown('</div>', unsafe_allow_html=True)
