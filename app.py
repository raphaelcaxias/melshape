"""
Melshape v3.0 — Entry Point Principal.

Arquitetura limpa, roteamento declarativo, injeção de dependências,
cache inteligente, tratamento de erros robusto e performance otimizada.

Princípios:
- Tudo que pode ser cacheado, é cacheado (@st.cache_resource)
- Tudo que pode ser lazy-loaded, é lazy-loaded
- Erros são tratados com gracefulness (nunca quebram a UI)
- Estado é gerenciado centralizadamente (sem variáveis globais)
- Dark mode persistente no banco
- Demo data carregado sob demanda
"""
from __future__ import annotations

import logging
from datetime import date, timedelta, datetime
from typing import Any, Callable

import streamlit as st

import config
from core.database import Database
from services.nutrition_service import NutritionService
from services.gamification_service import GamificationService
from services.food_service import FoodService
from services.plan_service import PlanService
from services.professional_service import ProfessionalService
from services.journey_service import JourneyService
from services.orchestrator import Orchestrator
from services.notification_service import NotificationService
from services.score_service import ScoreService
from services.contextualizer import ctx
from services.relapse_service import RelapseService

# ── LOGGING CONFIGURADO ──────────────────────────────────────────────────────
logging.basicConfig(
    level=config.LOG_LEVEL,
    format=config.LOG_FORMAT,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("Melshape")

# ── CONFIGURAÇÃO DA PÁGINA ──────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{config.APP_NAME} — {config.APP_TAGLINE}",
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": f"{config.APP_NAME} v{config.APP_VERSION} · {config.APP_TAGLINE}",
        "Report a bug": config.SUPPORT_EMAIL,
        "Get help": config.SUPPORT_EMAIL,
    },
)

# ── ESTADO DA SESSÃO ────────────────────────────────────────────────────────
def _init_session_state() -> None:
    """
    Inicializa o estado da sessão de forma segura.
    Evita o anti-padrão de usar classes customizadas para o st.session_state.
    """
    defaults: dict[str, Any] = {
        "user": None,
        "professional": None,
        "page": "landing",
        "perfil_id": None,
        "demo_loaded": False,
        "onboarding_step": 1,
        "onboarding_mode": "general",
        "pro_selected_patient": None,
        "reset_email_sent": False,
        "hub_tipo": "meal",
        "ci_result": None,
        "cs_resumo": None,
        "dark_mode": False,
    }
    
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
            
    # Mutables precisam de atenção especial para evitar compartilhamento de referência
    if "desafios_concluidos_local" not in st.session_state:
        st.session_state["desafios_concluidos_local"] = set()

# ── IMPORTS DAS VIEWS (Lazy Loading) ────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def _get_views() -> dict[str, Callable]:
    """
    Carrega e cacheia o dicionário de views.
    O cache_data garante que o dicionário não seja reconstruído a cada rerun.
    """
    # Imports locais para evitar circular imports e carregar sob demanda
    from views.auth import landing, login, register, forgot_password
    from views.shared import sidebar
    from views.patient import (
        home, onboarding, habits, goals, achievements, 
        glp1, bariatric, checkin, journey_story, profile
    )
    from views.patient.complete_evolution import render as evolution_view
    from views.patient.share_card import render as share_view
    from views.patient.register_hub import render as register_hub_view
    from views.patient.journey import render as journey_view
    from views.professional import dashboard_pro, patient_detail
    from views.professional.triage_panel import render_triagem
    from views.professional.executive_dashboard import render as executive_view
    
    return {
        # Auth
        "landing": landing.render,
        "login": login.render,
        "register": register.render,
        "register_pro": register.render,
        "forgot_password": forgot_password.render,
        
        # Patient
        "home": home.render,
        "dashboard": home.render,
        "onboarding": onboarding.render,
        "checkin": checkin.render,
        "meals": register_hub_view,
        "weight": register_hub_view,
        "journey": journey_view,
        "habits": habits.render,
        "supplements": habits.render,
        "workout": habits.render,
        "goals": goals.render,
        "analysis": achievements.render,
        "glp1": glp1.render,
        "bariatric": bariatric.render,
        "story": journey_story.render,
        "profile": profile.render,
        "evolution": evolution_view,
        "share": share_view,
        
        # Professional
        "pro_dashboard": dashboard_pro.render,
        "pro_patient_detail": patient_detail.render,
        "pro_triagem": render_triagem,
        "pro_executive": executive_view,
        
        # Shared
        "sidebar": sidebar.render,
    }

# ── INICIALIZAÇÃO DOS SERVIÇOS (Cached) ─────────────────────────────────────
@st.cache_resource(show_spinner=False, ttl=3600)
def _init_services() -> dict[str, Any]:
    """
    Inicializa todos os serviços com cache de recurso.
    Mantém as instâncias vivas entre os reruns do Streamlit.
    """
    logger.info(f"🚀 Inicializando {config.APP_NAME} v{config.APP_VERSION}...")
    
    db = Database()
    supabase_client = db.client if db.is_real else None
    
    services = {
        "db": db,
        "nutrition": NutritionService(db),
        "gamification": GamificationService(db),
        "foods": FoodService(supabase_client),
        "plan": PlanService(db),
        "professional": ProfessionalService(db),
        "journey": JourneyService(db),
        "orchestrator": Orchestrator(db),
        "notification": NotificationService(db),
        "score": ScoreService(db),
        "contextualizer": ctx,
        "relapse": RelapseService(db),
    }
    
    # Inicia agendador de notificações em background
    try:
        from services.notification_service import schedule_daily_reminders
        schedule_daily_reminders(db)
        logger.info("✅ Agendador de notificações iniciado")
    except Exception as e:
        logger.warning(f"⚠️ Agendador não iniciado: {e}")
    
    return services

# ── LOADER DE CSS E TEMA ────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _load_css() -> str:
    """Carrega CSS do arquivo com cache."""
    try:
        with open("assets/style.css", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("assets/style.css não encontrado.")
        return ""

def _apply_theme(dark_mode: bool) -> None:
    """Aplica o tema (claro/escuro) via JavaScript."""
    theme = "dark" if dark_mode else "light"
    st.markdown(
        f'<script>document.documentElement.setAttribute("data-theme","{theme}")</script>',
        unsafe_allow_html=True,
    )

# ── DEMO DATA ────────────────────────────────────────────────────────────────
def _load_demo_data(services: dict[str, Any]) -> None:
    """Carrega dados demo para o usuário demo (executado apenas uma vez)."""
    if st.session_state.demo_loaded:
        return
    
    user = st.session_state.user
    if not user or user.get("email") != config.DEMO_EMAIL:
        return
    
    db = services["db"]
    try:
        # Verificação rápida para não inserir dados duplicados
        if len(db.get_meals(30)) > 0:
            st.session_state.demo_loaded = True
            return
        
        from core.models import Meal, WeightLog
        
        demo_meals = [
            ("Peito de Frango Grelhado", 318, 64, 0, 7, 0, "12:30", 0, "almoco"),
            ("Arroz Integral Cozido", 248, 5.6, 52, 1.6, 3.4, "12:35", 0, "almoco"),
            ("Café com Leite", 120, 6, 12, 4, 0, "07:30", 0, "cafe_manha"),
            ("Proteína Whey", 120, 24, 3, 2, 0, "18:00", 0, "pre_pos_treino"),
            ("Banana Prata", 98, 1.3, 26, 0.1, 2, "15:30", 1, "lanche"),
            ("Tilápia Assada", 256, 52, 0, 5.4, 0, "12:30", 1, "almoco"),
            ("Aveia em Flocos", 360, 13, 64, 6.9, 9.4, "08:00", 2, "cafe_manha"),
        ]
        
        for food, cal, p, c, f, fi, t, d, tipo in demo_meals:
            db.save_meal(Meal(
                food=food, calories=cal, protein=p, carbs=c,
                fat=f, fiber=fi, meal_time=t, meal_type=tipo,
                meal_date=(date.today() - timedelta(days=d)).isoformat(),
            ))
        
        for i in range(30):
            db.save_weight(WeightLog(
                weight=round(82.0 - i * 0.14, 1),
                log_date=(date.today() - timedelta(days=29 - i)).isoformat(),
            ))
        
        st.session_state.demo_loaded = True
        logger.info("✅ Demo data carregado com sucesso")
    except Exception as e:
        logger.warning(f"Erro ao carregar demo data: {e}")

# ── ROTEADOR PRINCIPAL ──────────────────────────────────────────────────────
def _route(services: dict[str, Any]) -> None:
    """
    Roteamento principal com tratamento de erros e fluxo linear.
    """
    views = _get_views()
    page: str = st.session_state.page
    user: dict | None = st.session_state.user
    professional: dict | None = st.session_state.professional
    
    try:
        # 1. RESET DE SENHA VIA URL (Prioridade máxima)
        if "reset_token" in st.query_params and "email" in st.query_params:
            views["forgot_password"](services)
            return
        
        # 2. FLUXO DO PROFISSIONAL
        if professional:
            pro_pages = {"pro_patient_detail", "pro_triagem", "pro_executive"}
            target_view = views[page] if page in pro_pages else views["pro_dashboard"]
            
            if page == "pro_patient_detail":
                target_view(services, professional)
            else:
                target_view(services) if page in {"pro_triagem", "pro_executive"} else target_view(services, professional)
            return
        
        # 3. FLUXO NÃO AUTENTICADO
        if not user:
            auth_pages = {"landing", "login", "register", "register_pro", "forgot_password"}
            target_page = page if page in auth_pages else "landing"
            views[target_page](services)
            return
        
        # 4. FLUXO DO PACIENTE AUTENTICADO
        if user.get("email") == config.DEMO_EMAIL:
            _load_demo_data(services)
        
        # Onboarding obrigatório
        if not user.get("onboarding_done") or page == "onboarding":
            views["onboarding"](services, user)
            # Se acabou de completar o onboarding durante este rerun
            if st.session_state.get("user", {}).get("onboarding_done"):
                services["notification"].configurar_lembretes_iniciais(user)
            return
        
        # Redireciona páginas de auth para home se já estiver logado
        auth_pages = {"landing", "login", "register", "register_pro", "forgot_password"}
        if page in auth_pages:
            st.session_state.page = "home"
            st.rerun()
        
        # Renderiza Sidebar e Banner de Trial
        views["sidebar"](services)
        
        if page not in {"onboarding", "profile"}:
            services["plan"].trial_banner(user)
        
        # Renderiza a view do paciente
        view_fn = views.get(page)
        if view_fn:
            view_fn(services, user)
        else:
            logger.warning(f"Página desconhecida ou não mapeada: {page}")
            st.session_state.page = "home"
            st.rerun()
            
    except Exception as e:
        logger.error(f"Erro crítico no roteamento: {e}", exc_info=True)
        _render_error_page(e)

def _render_error_page(error: Exception) -> None:
    """Renderiza página de erro amigável (Graceful Degradation)."""
    st.markdown(
        f"""
        <div style="text-align:center;padding:4rem 2rem;">
            <div style="font-size:4rem;">🔥</div>
            <h1 style="font-family:var(--font-display);color:var(--text);">
                Algo deu errado
            </h1>
            <p style="color:var(--text-muted);max-width:500px;margin:1rem auto;">
                O Melshape encontrou um problema inesperado. 
                Nossa equipe já foi notificada.
            </p>
            <div style="background:var(--surface-2);border-radius:var(--radius-md);
                 padding:1rem;margin:1rem auto;max-width:600px;text-align:left;
                 font-size:0.82rem;color:var(--text-muted);">
                <strong>Erro:</strong> {str(error)[:200]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    if st.button("🔄 Tentar novamente", type="primary", use_container_width=True):
        st.rerun()

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main() -> None:
    """Ponto de entrada principal da aplicação."""
    # 1. Inicializa estado da sessão
    _init_session_state()
    
    # 2. Carrega CSS e aplica tema
    if css := _load_css():
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    
    if st.session_state.user and st.session_state.user.get("dark_mode"):
        _apply_theme(True)
    
    # 3. Inicializa serviços (sem usar variáveis globais)
    services = _init_services()
    
    # 4. Roteia a requisição
    _route(services)

if __name__ == "__main__":
    main()
