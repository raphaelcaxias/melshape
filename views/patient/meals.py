"""Melshape — Registro de refeições: ≤3 cliques, busca normalizada, repetir ontem."""
import streamlit as st
from datetime import date, datetime
from views.components import (
    empty_state, meal_item, alert, section_header,
    show_new_achievements, medical_disclaimer,
)
from utils.date_helpers import detect_meal_period, detect_meal_type
import config

MEAL_TYPES = [
    "Café da Manhã", "Almoço", "Lanche da Tarde",
    "Jantar", "Ceia", "Pré-Treino", "Pós-Treino",
]
MEAL_CAT = {
    "Café da Manhã":   "cafe_manha",
    "Almoço":          "almoco_jantar",
    "Lanche da Tarde": "lanche",
    "Jantar":          "almoco_jantar",
    "Ceia":            "ceia",
    "Pré-Treino":      "pre_pos_treino",
    "Pós-Treino":      "pre_pos_treino",
}
MOOD_OPTS = {
    "":        "😶 Sem humor",
    "great":   "😄 Ótimo",
    "good":    "🙂 Bom",
    "neutral": "😐 Neutro",
    "bad":     "😕 Ruim",
    "terrible":"😖 Péssimo",
}


def render(services: dict, user: dict) -> None:
    nutrition    = services["nutrition"]
    food_svc     = services["foods"]
    gamification = services["gamification"]
    plan_svc     = services["plan"]
    db           = services["db"]

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    section_header("🍴 Registro Alimentar",
                   f"{user.get('name','')} · {date.today().strftime('%d/%m/%Y')}")

    # ── VERIFICAR LIMITE ──────────────────────────────────────────────────
    can_add, limit_msg = plan_svc.check_meal_limit(user)
    if not can_add:
        current = db.count_meals_today()
        limit   = plan_svc.meals_limit_today(user)
        alert(f"{limit_msg} ({current}/{limit} registros)", "warning")
        plan_svc.show_paywall("Refeições ilimitadas", user)
        _show_today_summary(nutrition)
        medical_disclaimer()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── TIPO E HORÁRIO ────────────────────────────────────────────────────
    now_h = datetime.now().hour
    d_idx = (
        0 if 5  <= now_h < 10 else
        1 if now_h < 14 else
        2 if now_h < 18 else
        3 if now_h < 21 else 4
    )
    c1, c2 = st.columns([2, 1])
    with c1:
        tipo = st.selectbox("🍽️ Qual refeição?", MEAL_TYPES, index=d_idx)
    with c2:
        hora = st.time_input("⏰ Horário", value=datetime.now().time())

    cat     = MEAL_CAT.get(tipo, "lanche")
    periodo = detect_meal_period(int(hora.strftime("%H")))
    st.markdown(
        f'<div class="alert-info">🌅 <b>{periodo}</b> · Categoria: '
        f'{cat.replace("_", " ").title()}</div>',
        unsafe_allow_html=True,
    )

    # ── BOTÃO REPETIR ONTEM ───────────────────────────────────────────────
    from datetime import timedelta
    ontem_str  = (date.today() - timedelta(days=1)).isoformat()
    ontem_str2 = (date.today() - timedelta(days=1)).strftime("%d/%m")
    meals_yesterday = db.get_meals_by_date(ontem_str)
    if meals_yesterday:
        if st.button(
            f"🔄 Repetir refeições de ontem ({ontem_str2}) — {len(meals_yesterday)} itens",
            use_container_width=True,
        ):
            for m in meals_yesterday:
                from core.models import Meal
                new_meal = Meal(
                    food=m.food, calories=m.calories, protein=m.protein,
                    carbs=m.carbs, fat=m.fat, fiber=m.fiber,
                    quantity=m.quantity, volume_ml=m.volume_ml,
                    meal_time=m.meal_time, meal_type=m.meal_type,
                    nutrient_score=m.nutrient_score,
                )
                db.save_meal(new_meal)
            sm = nutrition.daily_summary()
            st.success(f"✅ {len(meals_yesterday)} refeições copiadas! Total: {sm['calories']} kcal")
            show_new_achievements(gamification.check_achievements(user))
            st.rerun()

    # ── BUSCA DE ALIMENTOS ────────────────────────────────────────────────
    frequent = nutrition.suggest_foods()
    c1, c2 = st.columns([3, 1])
    with c1:
        term = st.text_input(
            "🔍 Buscar alimento",
            placeholder="Ex: frango, arroz, banana... (busca sem acento)",
        )
    with c2:
        st.markdown("")
        show_all = st.checkbox("Todos", value=False)

    foods = (
        food_svc.search_foods(term, None if show_all else cat, frequent)
        if term
        else food_svc.get_foods_by_category(cat)
    )

    if not foods:
        empty_state("🥦", "Nenhum alimento encontrado",
                    "Tente outro termo (ex: 'frango', 'arroz')")
        medical_disclaimer()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── SELEÇÃO DO ALIMENTO ───────────────────────────────────────────────
    opts: dict = {}
    for a in foods:
        label = (
            f"{a.get('name','')} · {a.get('portion','100g')} "
            f"({a.get('calories',0)} kcal)"
        )
        opts[label] = a

    sel = st.selectbox("Selecione o alimento", sorted(opts.keys()))

    if sel:
        food = opts[sel]
        _food_form(food, hora, tipo, cat, nutrition, gamification, db, user)

    st.markdown("---")
    _show_today_summary(nutrition)
    medical_disclaimer()
    st.markdown('</div>', unsafe_allow_html=True)


def _food_form(food: dict, hora, tipo: str, cat: str,
               nutrition, gamification, db, user: dict) -> None:
    cal  = food.get("calories", 0)
    prot = food.get("protein", 0)
    carb = food.get("carbs", 0)
    fat  = food.get("fat", 0)
    fib  = food.get("fiber", 0)

    st.markdown(
        f'<div style="background:rgba(201,168,76,.08);border:1px solid rgba(201,168,76,.3);'
        f'border-radius:14px;padding:1rem;margin:0.5rem 0;">'
        f'<b style="font-family:Sora,sans-serif;">{food.get("name")}</b> · '
        f'{food.get("portion","100g")}<br>'
        f'<span style="font-size:0.83rem;color:#64748b;">'
        f'🔥 {cal} kcal · 🥩 {prot:.1f}g prot · 🍚 {carb:.1f}g carbs · '
        f'🧈 {fat:.1f}g gord · 🌿 {fib:.1f}g fibra'
        f'</span></div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        qtd  = st.number_input("Quantidade (porções)", 0.1, 10.0, 1.0, 0.1, format="%.1f")
    with c2:
        st.markdown("")
        meia = st.checkbox("½ porção")
    with c3:
        qf      = qtd * 0.5 if meia else qtd
        cal_tot = int(cal * qf)
        prt_tot = round(prot * qf, 1)
        st.markdown(
            f'<div style="background:#f0fdf4;border-radius:10px;padding:0.7rem;text-align:center;">'
            f'<div style="font-family:Sora,sans-serif;font-size:1.4rem;font-weight:700;color:#C9A84C;">'
            f'{cal_tot} kcal</div>'
            f'<div style="font-size:0.78rem;color:#64748b;">🥩 {prt_tot}g proteína</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Volume em ml para bariátrico
    volume_ml = 0.0
    mode = user.get("health_mode", "general")
    if mode == "bariatric":
        volume_ml = st.number_input(
            "Volume (ml) — controle de porção bariátrica",
            0.0, 1000.0, 150.0, 10.0,
        )
        phase = user.get("bariatric_phase", "")
        vol_alert = nutrition.bariatric_volume_alert(volume_ml, phase)
        if vol_alert:
            from views.components import alert
            alert(vol_alert, "bariatric")

    mood = st.selectbox(
        "😊 Como você está se sentindo?",
        list(MOOD_OPTS.keys()),
        format_func=lambda x: MOOD_OPTS[x],
    )

    meal_type = MEAL_CAT.get(tipo, "lanche")

    if st.button("✅ Registrar Refeição", type="primary", use_container_width=True):
        qf  = qtd * 0.5 if meia else qtd
        ok  = nutrition.register_meal(
            food, qf, hora.strftime("%H:%M"),
            meal_type, mood, volume_ml,
        )
        if ok:
            sm = nutrition.daily_summary()
            st.success(
                f"✅ **{food.get('name')}** registrado! "
                f"Total hoje: **{sm['calories']} kcal** · **{sm['protein']:.0f}g** prot"
            )
            st.balloons()
            from utils.motivational_quotes import get_quote
            from views.components import motivational_quote
            motivational_quote(get_quote("after_meal", user.get("health_mode", "general")))
            show_new_achievements(gamification.check_achievements(user))
            st.rerun()
        else:
            st.error("❌ Erro ao registrar. Tente novamente.")


def _show_today_summary(nutrition) -> None:
    sm = nutrition.daily_summary()
    st.markdown("**📋 Refeições de Hoje**")
    if sm["meals"]:
        st.markdown(
            f'<div style="background:rgba(201,168,76,.08);border-radius:10px;'
            f'padding:0.65rem 1rem;margin-bottom:0.5rem;font-size:0.83rem;color:#78350f;">'
            f'🔥 <b>{sm["calories"]} kcal</b> · 🥩 {sm["protein"]:.0f}g · '
            f'🍚 {sm["carbs"]:.0f}g · 🧈 {sm["fat"]:.0f}g · 🌿 {sm["fiber"]:.0f}g fibra'
            f'</div>',
            unsafe_allow_html=True,
        )
        for m in sm["meals"]:
            meal_item(m.meal_time, m.food, m.calories, m.nutrient_score)
    else:
        empty_state("🍽️", "Nenhuma refeição hoje", "Comece agora!")
