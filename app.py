"""
Melshape v3.0 — Entry Point Principal.

Arquitetura limpa, roteamento declarativo, injeção de dependências,
cache inteligente, tratamento de erros robusto e performance otimizada.

Arquitetura:
    AppInitializer
    ├── SessionManager (gerencia estado da sessão)
    ├── ServiceRegistry (registra e cacheia serviços)
    ├── ViewRegistry (lazy loading de views)
    ├── ThemeManager (gerencia tema CSS/dark mode)
    ├── DemoDataLoader (carrega dados demo sob demanda)
    └── Router (roteamento com Strategy Pattern)
        ├── AuthRouter
        ├── ProfessionalRouter
        └── PatientRouter

Princípios:
- Tudo que pode ser cacheado, é cacheado (@st.cache_resource/@st.cache_data)
- Tudo que pode ser lazy-loaded, é lazy-loaded
- Erros são tratados com gracefulness (nunca quebram a UI)
- Estado é gerenciado centralizadamente
- Dark mode persistente no banco
- Demo data carregado sob demanda
- Tipagem forte: Protocol, TypedDict, dataclasses
- Validação: dados validados antes de processar
- Logging: todas as operações críticas são logadas
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Protocol, TypedDict, runtime_checkable

import streamlit as st

import config
from core.database import Database
from services.contextualizer import ctx
from services.food_service import FoodService
from services.gamification_service import GamificationService
from services.journey_service import JourneyService
from services.notification_service import NotificationService
from services.nutrition_service import NutritionService
from services.orchestrator import Orchestrator
from services.plan_service import PlanService
from services.professional_service import ProfessionalService
from services.relapse_service import RelapseService
from services.score_service import ScoreService

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=config.LOG_LEVEL,
    format=config.LOG_FORMAT,
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("Melshape")


# ─────────────────────────────────────────────────────────────────────────────
# TIPOS
# ─────────────────────────────────────────────────────────────────────────────

class ServicesDict(TypedDict):
    """Dicionário tipado de serviços."""
    db: Database
    nutrition: NutritionService
    gamification: GamificationService
    foods: FoodService
    plan: PlanService
    professional: ProfessionalService
    journey: JourneyService
    orchestrator: Orchestrator
    notification: NotificationService
    score: ScoreService
    contextualizer: Any
    relapse: RelapseService


@runtime_checkable
class ViewFunction(Protocol):
    """Protocol para funções de view."""
    def __call__(self, services: ServicesDict, *args: Any, **kwargs: Any) -> None: ...


@dataclass(frozen=True)
class AppState:
    """Estado da aplicação (imutável)."""
    user: dict[str, Any] | None
    professional: dict[str, Any] | None
    page: str
    perfil_id: str | None
    demo_loaded: bool
    onboarding_step: int
    onboarding_mode: str
    dark_mode: bool
    
    @classmethod
    def from_session(cls) -> AppState:
        """Cria AppState a partir do session_state."""
        return cls(
            user=st.session_state.get("user"),
            professional=st.session_state.get("professional"),
            page=st.session_state.get("page", "landing"),
            perfil_id=st.session_state.get("perfil_id"),
            demo_loaded=st.session_state.get("demo_loaded", False),
            onboarding_step=st.session_state.get("onboarding_step", 1),
            onboarding_mode=st.session_state.get("onboarding_mode", "general"),
            dark_mode=st.session_state.get("dark_mode", False),
        )


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

_CACHE_TTL_SECONDS: int = 3600
_AUTH_PAGES: frozenset[str] = frozenset({
    "landing", "login", "register", "register_pro", "forgot_password"
})
_PRO_PAGES: frozenset[str] = frozenset({
    "pro_dashboard", "pro_patient_detail", "pro_triagem", "pro_executive"
})
_PATIENT_PAGES: frozenset[str] = frozenset({
    "home", "dashboard", "onboarding", "checkin", "meals", "weight",
    "journey", "habits", "supplements", "workout", "goals", "analysis",
    "glp1", "bariatric", "story", "profile", "evolution", "share"
})


# ─────────────────────────────────────────────────────────────────────────────
# SESSION MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class SessionManager:
    """Gerencia o estado da sessão de forma centralizada."""
    
    _DEFAULTS: dict[str, Any] = {
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
    
    @staticmethod
    def initialize() -> None:
        """Inicializa o estado da sessão com valores padrão."""
        for key, val in SessionManager._DEFAULTS.items():
            if key not in st.session_state:
                st.session_state[key] = val
        
        # Mutáveis precisam de atenção especial
        if "desafios_concluidos_local" not in st.session_state:
            st.session_state["desafios_concluidos_local"] = set()
    
    @staticmethod
    def get_state() -> AppState:
        """Retorna estado atual da aplicação."""
        return AppState.from_session()
    
    @staticmethod
    def update_page(page: str) -> None:
        """Atualiza página atual."""
        st.session_state.page = page
    
    @staticmethod
    def is_authenticated() -> bool:
        """Verifica se usuário está autenticado."""
        return st.session_state.user is not None
    
    @staticmethod
    def is_professional() -> bool:
        """Verifica se é profissional."""
        return st.session_state.professional is not None


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class ServiceRegistry:
    """Registra e cacheia serviços com injeção de dependências."""
    
    @staticmethod
    @st.cache_resource(show_spinner=False, ttl=_CACHE_TTL_SECONDS)
    def initialize() -> ServicesDict:
        """
        Inicializa todos os serviços com cache de recurso.
        Mantém as instâncias vivas entre os reruns do Streamlit.
        """
        logger.info(f"🚀 Inicializando {config.APP_NAME} v{config.APP_VERSION}...")
        
        db = Database()
        supabase_client = db.client if db.is_real else None
        
        services: ServicesDict = {
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
        ServiceRegistry._start_notification_scheduler(db)
        
        return services
    
    @staticmethod
    def _start_notification_scheduler(db: Database) -> None:
        """Inicia agendador de notificações com tratamento de erros."""
        try:
            from services.notification_service import schedule_daily_reminders
            schedule_daily_reminders(db)
            logger.info("✅ Agendador de notificações iniciado")
        except Exception as e:
            logger.warning(f"⚠️ Agendador não iniciado: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# VIEW REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class ViewRegistry:
    """Lazy loading e cache de views."""
    
    @staticmethod
    @st.cache_data(show_spinner=False, ttl=_CACHE_TTL_SECONDS)
    def get_views() -> dict[str, ViewFunction]:
        """
        Carrega e cacheia o dicionário de views.
        Imports locais para evitar circular imports e carregar sob demanda.
        """
        # Auth
        from views.auth import forgot_password, landing, login, register
        
        # Shared
        from views.shared import sidebar
        
        # Patient
        from views.patient import (
            bariatric,
            checkin,
            glp1,
            goals,
            habits,
            home,
            journey_story,
            onboarding,
            profile,
        )
        from views.patient import achievements
        from views.patient.complete_evolution import render as evolution_view
        from views.patient.journey import render as journey_view
        from views.patient.register_hub import render as register_hub_view
        from views.patient.share_card import render as share_view
        
        # Professional
        from views.professional import dashboard_pro, patient_detail
        from views.professional.executive_dashboard import render as executive_view
        from views.professional.triage_panel import render_triagem
        from patient.score_view import render as score_view
        from patient.prescricoes_view import render as prescricoes_view
        from patient.evolucao_visual import render as evolucao_visual
        from professional.onboarding_pro import render as pro_onboarding_view
        from professional.patients_list import render as pro_pacientes_view
        
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
            "pro_convite": __import__("professional.patient_invite", fromlist=["render"]).render,
            "score": score_view,
            "prescricoes": prescricoes_view,
            "evolucao_visual": evolucao_visual,
            "pro_onboarding": pro_onboarding_view,
            "pro_pacientes": pro_pacientes_view,
            # Shared
            "sidebar": sidebar.render,
        }


# ─────────────────────────────────────────────────────────────────────────────
# THEME MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class ThemeManager:
    """Gerencia tema CSS e dark mode."""
    
    @staticmethod
    @st.cache_data(ttl=_CACHE_TTL_SECONDS, show_spinner=False)
    def load_css() -> str:
        """Carrega CSS do arquivo com cache."""
        try:
            with open("assets/style.css", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("assets/style.css não encontrado.")
            return ""
    
    @staticmethod
    def apply(dark_mode: bool) -> None:
        """Aplica o tema (claro/escuro) via JavaScript."""
        theme = "dark" if dark_mode else "light"
        st.markdown(
            f'<script>document.documentElement.setAttribute("data-theme","{theme}")</script>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# DEMO DATA LOADER
# ─────────────────────────────────────────────────────────────────────────────

class DemoDataLoader:
    """Carrega dados demo para o usuário demo sob demanda."""
    
    _DEMO_MEALS: tuple[tuple[str, int, float, float, float, float, str, int, str], ...] = (
        ("Peito de Frango Grelhado", 318, 64, 0, 7, 0, "12:30", 0, "almoco"),
        ("Arroz Integral Cozido", 248, 5.6, 52, 1.6, 3.4, "12:35", 0, "almoco"),
        ("Café com Leite", 120, 6, 12, 4, 0, "07:30", 0, "cafe_manha"),
        ("Proteína Whey", 120, 24, 3, 2, 0, "18:00", 0, "pre_pos_treino"),
        ("Banana Prata", 98, 1.3, 26, 0.1, 2, "15:30", 1, "lanche"),
        ("Tilápia Assada", 256, 52, 0, 5.4, 0, "12:30", 1, "almoco"),
        ("Aveia em Flocos", 360, 13, 64, 6.9, 9.4, "08:00", 2, "cafe_manha"),
    )
    
    @staticmethod
    def load_if_needed(services: ServicesDict) -> None:
        """Carrega dados demo se necessário."""
        state = SessionManager.get_state()
        
        if state.demo_loaded:
            return
        
        if not state.user or state.user.get("email") != config.DEMO_EMAIL:
            return
        
        db = services["db"]
        
        # Verificação rápida para não inserir dados duplicados
        if len(db.get_meals(30)) > 0:
            st.session_state.demo_loaded = True
            return
        
        try:
            DemoDataLoader._insert_demo_data(db)
            st.session_state.demo_loaded = True
            logger.info("✅ Demo data carregado com sucesso")
        except Exception as e:
            logger.warning(f"Erro ao carregar demo data: {e}")
    
    @staticmethod
    def _insert_demo_data(db: Database) -> None:
        """Insere dados demo no banco."""
        from core.models import Meal, WeightLog
        
        # Insere refeições demo
        for food, cal, p, c, f, fi, t, d, tipo in DemoDataLoader._DEMO_MEALS:
            db.save_meal(Meal(
                food=food,
                calories=cal,
                protein=p,
                carbs=c,
                fat=f,
                fiber=fi,
                meal_time=t,
                meal_type=tipo,
                meal_date=(date.today() - timedelta(days=d)).isoformat(),
            ))
        
        # Insere pesos demo (30 dias)
        for i in range(30):
            db.save_weight(WeightLog(
                weight=round(82.0 - i * 0.14, 1),
                log_date=(date.today() - timedelta(days=29 - i)).isoformat(),
            ))


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER (Strategy Pattern)
# ─────────────────────────────────────────────────────────────────────────────

class Router:
    """Roteamento principal com Strategy Pattern."""
    
    def __init__(self, services: ServicesDict) -> None:
        self.services = services
        self.views = ViewRegistry.get_views()
    
    def route(self) -> None:
        """Roteia a requisição com tratamento de erros."""
        try:
            self._handle_routing()
        except Exception as e:
            logger.error(f"Erro crítico no roteamento: {e}", exc_info=True)
            self._render_error_page(e)
    
    def _handle_routing(self) -> None:
        """Lógica de roteamento principal."""
        state = SessionManager.get_state()
        
        # 1. RESET DE SENHA VIA URL (Prioridade máxima)
        if self._is_password_reset_request():
            self.views["forgot_password"](self.services)
            return
        
        # 2. FLUXO DO PROFISSIONAL
        if state.professional:
            self._route_professional(state)
            return
        
        # 3. FLUXO NÃO AUTENTICADO
        if not state.user:
            self._route_unauthenticated(state)
            return
        
        # 4. FLUXO DO PACIENTE AUTENTICADO
        self._route_authenticated_patient(state)
    
    def _is_password_reset_request(self) -> bool:
        """Verifica se é requisição de reset de senha."""
        return "reset_token" in st.query_params and "email" in st.query_params
    
    def _route_professional(self, state: AppState) -> None:
        """Roteia fluxo do profissional."""
        page = state.page
        professional = state.professional

        # Onboarding obrigatório no primeiro acesso (Sprint 3)
        onboarding_done = (
            professional.get("onboarding_done", False)
            if isinstance(professional, dict)
            else getattr(professional, "onboarding_done", False)
        )
        if not onboarding_done and page != "pro_convite":
            self.views["pro_onboarding"](self.services, professional)
            return

        if page == "pro_patient_detail":
            self.views["pro_patient_detail"](self.services, state.professional)
        elif page == "pro_triagem":
            self.views["pro_triagem"](self.services)
        elif page == "pro_executive":
            self.views["pro_executive"](self.services)
        elif page == "pro_convite":
            self.views["pro_convite"](self.services, state.professional)
        elif page == "pro_pacientes":
            self.views["pro_pacientes"](self.services, state.professional)
        else:
            self.views["pro_dashboard"](self.services, state.professional)
    
    def _route_unauthenticated(self, state: AppState) -> None:
        """Roteia fluxo não autenticado."""
        target_page = state.page if state.page in _AUTH_PAGES else "landing"
        self.views[target_page](self.services)
    
    def _route_authenticated_patient(self, state: AppState) -> None:
        """Roteia fluxo do paciente autenticado."""
        # Carrega demo data se necessário
        DemoDataLoader.load_if_needed(self.services)

        # Sprint 6: rastreamento de uso — page_view (falha silenciosa)
        try:
            from services.analytics_service import EventTracker
            uid = state.user.get("email", "") if isinstance(state.user, dict) else getattr(state.user, "email", "")
            EventTracker(self.services.get("db"), uid).page_view(state.page)
        except Exception:
            pass

        # Onboarding obrigatório
        if not state.user.get("onboarding_done") or state.page == "onboarding":
            self._handle_onboarding(state)
            return

        # Redireciona páginas de auth para home se já estiver logado
        if state.page in _AUTH_PAGES:
            SessionManager.update_page("home")
            st.rerun()
        
        # Renderiza UI do paciente
        self._render_patient_ui(state)
    
    def _handle_onboarding(self, state: AppState) -> None:
        """Gerencia fluxo de onboarding."""
        self.views["onboarding"](self.services, state.user)
        
        # Se acabou de completar o onboarding durante este rerun
        if st.session_state.get("user", {}).get("onboarding_done"):
            pass  # agendador ja iniciado em ServiceRegistry.initialize()
    
    def _render_patient_ui(self, state: AppState) -> None:
        """Renderiza UI do paciente."""
        # Sidebar
        self.views["sidebar"](self.services)
        
        # Banner de trial (exceto em onboarding/profile)
        if state.page not in {"onboarding", "profile"}:
            self.services["plan"].trial_banner(state.user)
        
        # View da página
        view_fn = self.views.get(state.page)
        if view_fn:
            view_fn(self.services, state.user)
        else:
            logger.warning(f"Página desconhecida ou não mapeada: {state.page}")
            SessionManager.update_page("home")
            st.rerun()
    
    def _render_error_page(self, error: Exception) -> None:
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


# ─────────────────────────────────────────────────────────────────────────────
# APP INITIALIZER
# ─────────────────────────────────────────────────────────────────────────────

class AppInitializer:
    """Inicializa a aplicação com todas as dependências."""
    
    @staticmethod
    def setup_page_config() -> None:
        """Configura a página Streamlit."""
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
    
    @staticmethod
    def apply_theme() -> None:
        """Aplica tema CSS e dark mode."""
        if css := ThemeManager.load_css():
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
        
        state = SessionManager.get_state()
        if state.user and state.dark_mode:
            ThemeManager.apply(dark_mode=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Ponto de entrada principal da aplicação."""
    # 1. Configura página
    AppInitializer.setup_page_config()
    
    # 2. Inicializa estado da sessão
    SessionManager.initialize()
    
    # 3. Aplica tema
    AppInitializer.apply_theme()
    
    # 4. Inicializa serviços
    services = ServiceRegistry.initialize()
    
    # 5. Roteia a requisição
    router = Router(services)
    router.route()


if __name__ == "__main__":
    main()
