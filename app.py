"""
Melshape v2.0 — Entry point principal.
Inclui: recuperação de senha via URL, notificações agendadas,
        cache de serviços e gestão completa de sessão.
"""
import logging
import streamlit as st

import config
from core.database import Database
from services.nutrition_service import NutritionService
from services.gamification_service import GamificationService
from services.food_service import FoodService
from services.plan_service import PlanService
from services.professional_service import ProfessionalService

# Views
from views.auth import landing as landing_view
from views.auth import login as login_view
from views.auth import register as register_view
from views.auth import forgot_password as forgot_password_view
from views.shared import sidebar as sidebar_view
from views.patient import (
    onboarding as onboarding_view,
    home as home_view,
    dashboard as dashboard_view,
    meals as meals_view,
    weight as weight_view,
    supplements as supplements_view,
    workout as workout_view,
    analysis as analysis_view,
    profile as profile_view,
)
from views.professional import dashboard_pro as pro_dashboard_view
from views.professional import patient_detail as patient_detail_view
from views.vitrine import showcase as showcase_view

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger("Melshape")

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{config.APP_NAME} — {config.APP_TAGLINE}",
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": f"{config.APP_NAME} v{config.APP_VERSION} · {config.APP_TAGLINE}",
        "Report a bug": "https://melshape.com.br/suporte",
    },
)

# ── Sessão ────────────────────────────────────────────────────────────────────
_SESSION_DEFAULTS = {
    "user":                 None,
    "professional":         None,
    "page":                 "landing",
    "demo_loaded":          False,
    "onboarding_step":      1,
    "onboarding_mode":      "general",
    "pro_page":             "pro_patients",
    "pro_selected_patient": None,
    "reset_email_sent":     False,
    "confirm_delete":       False,
}


def _init_session() -> None:
    for key, val in _SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _clear_session() -> None:
    """Limpa toda a sessão no logout."""
    for key in list(_SESSION_DEFAULTS.keys()):
        st.session_state.pop(key, None)
    st.query_params.clear()
    st.session_state.page = "landing"
    st.rerun()


# ── CSS ───────────────────────────────────────────────────────────────────────
def _load_css() -> None:
    try:
        with open("assets/style.css", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        logger.warning("assets/style.css não encontrado.")


# ── Serviços (cache global — roda uma vez por sessão de servidor) ─────────────
@st.cache_resource(show_spinner=False)
def _init_services() -> dict:
    logger.info("🚀 Inicializando serviços Melshape v2...")
    db = Database()

    supabase_client = None
    try:
        if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
            from supabase import create_client
            supabase_client = create_client(
                st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
            )
    except Exception:
        pass

    services = {
        "db":           db,
        "nutrition":    NutritionService(db),
        "gamification": GamificationService(db),
        "foods":        FoodService(supabase_client),
        "plan":         PlanService(db),
        "professional": ProfessionalService(db),
    }

    # Inicia agendador de notificações em background
    try:
        from services.notification_service import schedule_daily_reminders
        schedule_daily_reminders(db)
    except Exception as e:
        logger.warning(f"Agendador não iniciado: {e}")

    return services


# ── Dados demo ────────────────────────────────────────────────────────────────
def _load_demo_data(services: dict) -> None:
    if st.session_state.get("demo_loaded"):
        return
    u = st.session_state.get("user")
    if not u or u.get("email") != config.DEMO_EMAIL:
        return
    db = services["db"]
    if len(db.get_meals(30)) > 0:
        st.session_state.demo_loaded = True
        return

    from datetime import date, timedelta
    from core.models import Meal, WeightLog, Supplement, WorkoutLog, HydrationLog, SleepLog

    demo_meals = [
        {"food":"Peito de Frango Grelhado","cal":318,"p":64,"c":0,  "f":7,  "fi":0,   "t":"12:30","d":0,"tipo":"almoco"},
        {"food":"Arroz Integral Cozido",   "cal":248,"p":5.6,"c":52,"f":1.6,"fi":3.4, "t":"12:35","d":0,"tipo":"almoco"},
        {"food":"Feijão Preto Cozido",     "cal":154,"p":9,  "c":28,"f":1,  "fi":12.6,"t":"12:40","d":0,"tipo":"almoco"},
        {"food":"Café com Leite",          "cal":120,"p":6,  "c":12,"f":4,  "fi":0,   "t":"07:30","d":0,"tipo":"cafe_manha"},
        {"food":"Proteína Whey",           "cal":120,"p":24, "c":3, "f":2,  "fi":0,   "t":"18:00","d":0,"tipo":"pre_pos_treino"},
        {"food":"Banana Prata",            "cal":98, "p":1.3,"c":26,"f":0.1,"fi":2,   "t":"15:30","d":1,"tipo":"lanche"},
        {"food":"Aveia em Flocos",         "cal":360,"p":13, "c":64,"f":6.9,"fi":9.4, "t":"08:00","d":1,"tipo":"cafe_manha"},
        {"food":"Tilápia Assada",          "cal":256,"p":52, "c":0, "f":5.4,"fi":0,   "t":"12:30","d":1,"tipo":"almoco"},
        {"food":"Proteína Whey",           "cal":120,"p":24, "c":3, "f":2,  "fi":0,   "t":"18:00","d":1,"tipo":"pre_pos_treino"},
        {"food":"Iogurte Grego",           "cal":115,"p":8.5,"c":4, "f":6.5,"fi":0,   "t":"08:10","d":2,"tipo":"cafe_manha"},
        {"food":"Peito de Frango Grelhado","cal":318,"p":64, "c":0, "f":7,  "fi":0,   "t":"13:00","d":2,"tipo":"almoco"},
        {"food":"PF: Arroz+Feijão+Frango", "cal":520,"p":38, "c":64,"f":8,  "fi":6,   "t":"12:30","d":3,"tipo":"almoco"},
        {"food":"Proteína Whey",           "cal":120,"p":24, "c":3, "f":2,  "fi":0,   "t":"18:00","d":3,"tipo":"pre_pos_treino"},
        {"food":"Peito de Frango Grelhado","cal":318,"p":64, "c":0, "f":7,  "fi":0,   "t":"12:30","d":4,"tipo":"almoco"},
        {"food":"Arroz Branco Cozido",     "cal":256,"p":5,  "c":56,"f":0.4,"fi":0.4, "t":"12:35","d":4,"tipo":"almoco"},
        {"food":"Café com Leite",          "cal":120,"p":6,  "c":12,"f":4,  "fi":0,   "t":"07:30","d":5,"tipo":"cafe_manha"},
        {"food":"PF: Arroz+Feijão+Frango", "cal":520,"p":38, "c":64,"f":8,  "fi":6,   "t":"13:00","d":5,"tipo":"almoco"},
        {"food":"Aveia em Flocos",         "cal":360,"p":13, "c":64,"f":6.9,"fi":9.4, "t":"08:00","d":6,"tipo":"cafe_manha"},
        {"food":"Tilápia Assada",          "cal":256,"p":52, "c":0, "f":5.4,"fi":0,   "t":"12:30","d":6,"tipo":"almoco"},
    ]

    for m in demo_meals:
        db.save_meal(Meal(
            food=m["food"], calories=m["cal"], protein=m["p"],
            carbs=m["c"], fat=m["f"], fiber=m["fi"],
            meal_time=m["t"], meal_type=m["tipo"],
            meal_date=(date.today() - timedelta(days=m["d"])).isoformat(),
        ))

    for i in range(56):
        day = date.today() - timedelta(days=55 - i)
        db.save_weight(WeightLog(
            weight=round(82.0 - (i * 0.14), 1),
            log_date=day.isoformat(),
            notes="Início" if i == 0 else "",
        ))

    db.save_supplement(Supplement(name="Proteína Whey", dose="30", unit="g",
                                   category="protein", time_taken="18:00"))
    db.save_supplement(Supplement(name="Vitamina D3", dose="2000", unit="UI",
                                   category="vitamin", time_taken="08:00"))
    db.save_workout(WorkoutLog(
        workout_type="strength", muscle_group="legs",
        intensity="heavy", duration_min=60,
    ))
    db.save_hydration(HydrationLog(amount_ml=500, log_time="08:00"))
    db.save_hydration(HydrationLog(amount_ml=300, log_time="12:00"))
    db.save_hydration(HydrationLog(amount_ml=400, log_time="16:00"))
    db.save_sleep(SleepLog(hours=7.5, quality=4))

    st.session_state.demo_loaded = True
    logger.info("✅ Dados demo carregados!")


# ── Roteamento ────────────────────────────────────────────────────────────────
PATIENT_ROUTES = {
    "home":        home_view,
    "dashboard":   dashboard_view,
    "meals":       meals_view,
    "weight":      weight_view,
    "supplements": supplements_view,
    "workout":     workout_view,
    "analysis":    analysis_view,
    "profile":     profile_view,
}


def _check_url_reset_token() -> bool:
    """
    Verifica se a URL contém token de reset de senha.
    Retorna True se deve mostrar tela de redefinição.
    """
    params = st.query_params
    return "reset_token" in params and "email" in params


def main() -> None:
    try:
        _init_session()
        _load_css()
        services = _init_services()

        # ── RECUPERAÇÃO DE SENHA VIA URL ──────────────────────────────────
        if _check_url_reset_token():
            forgot_password_view.render(services)
            return

        # ── VITRINE ───────────────────────────────────────────────────────
        if st.session_state.page == "showcase":
            showcase_view.render()
            return

        # ── PROFISSIONAL ──────────────────────────────────────────────────
        if st.session_state.professional:
            pro  = st.session_state.professional
            page = st.session_state.page
            if page == "pro_patient_detail":
                patient_detail_view.render(services, pro)
            else:
                pro_dashboard_view.render(services, pro)
            return

        # ── NÃO AUTENTICADO ───────────────────────────────────────────────
        user = st.session_state.user
        if not user:
            page = st.session_state.page
            if page == "forgot_password":
                forgot_password_view.render(services)
            else:
                landing_view.render(services)
            return

        # ── DEMO ──────────────────────────────────────────────────────────
        if user.get("email") == config.DEMO_EMAIL:
            _load_demo_data(services)

        # ── ONBOARDING ────────────────────────────────────────────────────
        page = st.session_state.page
        if not user.get("onboarding_done") or page == "onboarding":
            onboarding_view.render(services, user)
            return

        # ── REDIRECIONA AUTH → HOME ───────────────────────────────────────
        if page in ("landing", "login", "register", "register_pro", "forgot_password"):
            st.session_state.page = "home"
            st.rerun()

        # ── PREFERÊNCIAS DE NOTIFICAÇÃO NO PERFIL ─────────────────────────
        # (verificação de trial expirando via banner na sidebar)

        # ── SIDEBAR + CONTEÚDO ────────────────────────────────────────────
        sidebar_view.render(services)

        view = PATIENT_ROUTES.get(page)
        if view:
            view.render(services, user)
        else:
            logger.warning(f"Página desconhecida: {page}")
            st.session_state.page = "home"
            st.rerun()

    except Exception as e:
        logger.error(f"Erro crítico em main(): {e}", exc_info=True)
        st.error(
            "⚠️ Ocorreu um erro inesperado. Por favor, recarregue a página. "
            "Se o problema persistir, entre em contato: suporte@melshape.com.br"
        )
        if st.button("🔄 Recarregar"):
            st.rerun()


if __name__ == "__main__":
    main()
