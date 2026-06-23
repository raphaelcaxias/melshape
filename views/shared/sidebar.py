"""
Melshape — Sidebar do paciente.
Menu: Jornada, Check-in, Registrar, Evolução, Conquistas + pilar + perfil.
Dark mode com persistência no banco.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

import config
from views.shared.sidebar_nav import render_pilar_perfil, _clear_session

logger = logging.getLogger("Melshape.Sidebar")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
@dataclass
class MenuItem:
    """Item do menu da sidebar."""
    icon: str
    label: str
    key: str
    page: str


@dataclass
class SidebarStats:
    """Estatísticas rápidas da sidebar."""
    calories: int = 0
    protein: float = 0.0
    hydration: int = 0
    streak: int = 0
    xp: int = 0
    level_number: int = 1
    level_name: str = "Iniciante"
    level_icon: str = "🌱"
    progress_pct: int = 0
    next_level: Optional[str] = None


# Menu principal
MENU_ITEMS = [
    MenuItem("🏠", "Home", "home", "home"),
    MenuItem("🗺️", "Jornada", "journey", "journey"),
    MenuItem("✅", "Check-in", "checkin", "checkin"),
    MenuItem("➕", "Registrar", "meals", "meals"),
    MenuItem("📋", "Hábitos", "habits", "habits"),
    MenuItem("🎯", "Metas", "goals", "goals"),
    MenuItem("📈", "Evolução", "dashboard", "dashboard"),
    MenuItem("🏆", "Conquistas", "analysis", "analysis"),
]

# Mapeamento de modos de saúde
MODE_LABELS = {
    "general": ("⚖️", "Emagrecimento", "general"),
    "fitness": ("💪", "Fitness", "fitness"),
    "bariatric": ("🔪", "Pós-Bariátrica", "bariatric"),
    "glp1": ("💉", "GLP-1", "glp1"),
}

# Mapeamento de planos
PLAN_LABELS = {
    "free": "🆓 FREE",
    "essencial": "💎 ESSENCIAL",
    "pro": "⭐ PRO",
    "lifetime": "👑 VITALÍCIO",
}

# Pilares específicos para navegação
PILAR_MAP = {
    "glp1": ("💉", "GLP-1", "glp1"),
    "bariatric": ("🔪", "Bariátrica", "bariatric"),
    "fitness": ("💪", "Fitness", "dashboard"),
}

# Fallbacks
DEFAULT_MODE = ("⚖️", "Emagrecimento", "general")
DEFAULT_PLAN = "🆓 FREE"
DEFAULT_LEVEL = "Iniciante"
DEFAULT_LEVEL_ICON = "🌱"


class SidebarRenderer:
    """Renderer dedicado para a sidebar do paciente."""
    
    def __init__(self, services: Dict[str, Any]):
        self.services = services or {}
        self.db = services.get("db")
        self.nutr = services.get("nutrition")
        self.gami = services.get("gamification")
        self.plan = services.get("plan")
        self.user = self._get_user()
        self.current_page = self._get_current_page()
        self.dark_mode = self._get_dark_mode()
    
    def _get_user(self) -> Dict[str, Any]:
        """Obtém usuário do session state de forma segura."""
        try:
            return st.session_state.get("user", {})
        except Exception as e:
            logger.error(f"Erro ao obter usuário: {e}")
            return {}
    
    def _get_current_page(self) -> str:
        """Obtém página atual de forma segura."""
        try:
            return st.session_state.get("page", "home")
        except Exception as e:
            logger.error(f"Erro ao obter página atual: {e}")
            return "home"
    
    def _get_dark_mode(self) -> bool:
        """Obtém configuração de dark mode."""
        try:
            return bool(self.user.get("dark_mode", False))
        except Exception as e:
            logger.debug(f"Erro ao obter dark mode: {e}")
            return False
    
    def render(self) -> None:
        """Renderiza sidebar completa."""
        try:
            # Aplica dark mode
            self._apply_dark_mode()
            
            with st.sidebar:
                # Logo
                self._render_logo()
                
                # Informações do usuário
                self._render_user_info()
                
                # Banner do trial
                self._render_trial_banner()
                
                # Stats rápidos
                self._render_quick_stats()
                
                # XP / Nível
                self._render_xp_progress()
                
                # Menu principal
                self._render_main_menu()
                
                # Navegação contextual do pilar + perfil
                self._render_pilar_perfil()
                
                # Evolução completa
                self._render_evolution_button()
                
                # Compartilhar conquista
                self._render_share_button()
                
                # Dark mode toggle
                self._render_dark_mode_toggle()
                
                # Sair
                self._render_logout_button()
                
                # Modo demo
                self._render_demo_badge()
        except Exception as e:
            logger.error(f"Erro ao renderizar sidebar: {e}", exc_info=True)
            st.sidebar.error("❌ Erro ao carregar menu")
    
    def _apply_dark_mode(self) -> None:
        """Aplica o tema dark/light na página."""
        try:
            theme = "dark" if self.dark_mode else "light"
            st.markdown(
                f"""
                <script>
                    document.documentElement.setAttribute("data-theme", "{theme}");
                </script>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao aplicar dark mode: {e}", exc_info=True)
    
    def _render_logo(self) -> None:
        """Renderiza o logo da aplicação."""
        st.markdown(
            """
            <div class="sidebar-logo">
                <div style="font-size: 2rem;">🔥</div>
                <div class="sidebar-logo-name">Melshape</div>
                <div class="sidebar-logo-tag">Para quem está mudando de verdade.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_user_info(self) -> None:
        """Renderiza informações do usuário."""
        try:
            health_mode = self.user.get("health_mode", "general")
            icon, label, css_class = self._get_mode_info(health_mode)
            
            # Plano efetivo
            effective_plan, plan_label = self._get_plan_info()
            
            st.markdown(
                f"""
                <div style="padding: 0 0.2rem; margin-bottom: 0.7rem;">
                    <div style="font-size: 0.90rem; font-weight: 700;
                        color: var(--text); margin-bottom: 0.3rem;">
                        👤 {self.user.get("name", "Usuário")}
                    </div>
                    <span class="mode-badge mode-{css_class}">{icon} {label}</span>
                    &nbsp;<span class="plan-{effective_plan}">{plan_label}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar info do usuário: {e}", exc_info=True)
    
    def _get_mode_info(self, health_mode: str) -> tuple:
        """Obtém informações do modo de saúde."""
        try:
            return MODE_LABELS.get(health_mode, DEFAULT_MODE)
        except Exception as e:
            logger.debug(f"Erro ao obter modo info: {e}")
            return DEFAULT_MODE
    
    def _get_plan_info(self) -> tuple:
        """Obtém informações do plano do usuário."""
        try:
            from core.models import User
            user_obj = User.from_dict(self.user)
            effective_plan = user_obj.effective_plan()
            plan_label = self._get_plan_label(effective_plan, user_obj)
            return effective_plan, plan_label
        except Exception as e:
            logger.error(f"Erro ao obter plano: {e}", exc_info=True)
            return "free", DEFAULT_PLAN
    
    def _get_plan_label(self, effective_plan: str, user_obj) -> str:
        """Obtém o label do plano."""
        try:
            if effective_plan == "trial":
                trial_days = user_obj.trial_days_remaining()
                return f"⏳ TRIAL ({trial_days}d)"
            return PLAN_LABELS.get(effective_plan, DEFAULT_PLAN)
        except Exception as e:
            logger.debug(f"Erro ao obter label do plano: {e}")
            return DEFAULT_PLAN
    
    def _render_trial_banner(self) -> None:
        """Renderiza banner de trial com tratamento de erros."""
        try:
            if self.plan and hasattr(self.plan, "trial_banner"):
                self.plan.trial_banner(self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar banner trial: {e}", exc_info=True)
    
    def _render_quick_stats(self) -> None:
        """Renderiza estatísticas rápidas."""
        stats = self._get_quick_stats()
        
        st.markdown(
            f"""
            <div style="display: grid; grid-template-columns: 1fr 1fr;
                gap: 0.45rem; margin: 0.7rem 0;">
                <div class="metric-card">
                    <div class="metric-value" style="font-size: 1.3rem;">
                        {stats.calories}
                    </div>
                    <div class="metric-label">🔥 kcal hoje</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" style="font-size: 1.3rem;">
                        {stats.protein:.0f}g
                    </div>
                    <div class="metric-label">🥩 proteína</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" style="font-size: 1.3rem;">
                        {stats.hydration}ml
                    </div>
                    <div class="metric-label">💧 água</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" style="font-size: 1.3rem;">
                        {stats.streak}d
                    </div>
                    <div class="metric-label">📅 sequência</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    @st.cache_data(ttl=30)
    def _get_quick_stats(_self) -> SidebarStats:
        """Obtém estatísticas rápidas com cache."""
        try:
            # Daily summary
            daily_summary = _self._get_daily_summary()
            
            # Hydration
            hydration = _self._get_hydration()
            
            # Gamification stats
            gami_stats = _self._get_gami_stats()
            
            return SidebarStats(
                calories=daily_summary.get("calories", 0),
                protein=daily_summary.get("protein", 0.0),
                hydration=hydration,
                streak=_self._parse_int(gami_stats.get("streak", 0)),
                xp=_self._parse_int(gami_stats.get("xp", 0)),
                level_number=_self._parse_int(gami_stats.get("level_number", 1)),
                level_name=gami_stats.get("level_name", DEFAULT_LEVEL),
                level_icon=gami_stats.get("level_icon", DEFAULT_LEVEL_ICON),
                progress_pct=_self._parse_int(gami_stats.get("progress_pct", 0)),
                next_level=gami_stats.get("next_level"),
            )
        except Exception as e:
            logger.error(f"Erro ao obter quick stats: {e}", exc_info=True)
            return SidebarStats()
    
    def _get_daily_summary(self) -> Dict[str, Any]:
        """Obtém resumo diário de nutrição."""
        if not self.nutr:
            return {}
        
        try:
            summary = self.nutr.daily_summary()
            return summary if isinstance(summary, dict) else {}
        except Exception as e:
            logger.error(f"Erro ao obter daily summary: {e}", exc_info=True)
            return {}
    
    def _get_hydration(self) -> int:
        """Obtém hidratação de hoje."""
        if not self.db:
            return 0
        
        try:
            hydration = self.db.get_hydration_today()
            return int(hydration) if hydration is not None else 0
        except Exception as e:
            logger.error(f"Erro ao obter hidratação: {e}", exc_info=True)
            return 0
    
    def _get_gami_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de gamificação."""
        if not self.gami:
            return {}
        
        try:
            stats = self.gami.quick_stats()
            return stats if isinstance(stats, dict) else {}
        except Exception as e:
            logger.error(f"Erro ao obter gami stats: {e}", exc_info=True)
            return {}
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _render_xp_progress(self) -> None:
        """Renderiza barra de progresso de XP."""
        stats = self._get_quick_stats()
        
        next_label = f"→ {stats.next_level}" if stats.next_level else "MAX"
        progress_pct = min(100, max(0, stats.progress_pct))
        
        st.markdown(
            f"""
            <div style="margin-bottom: 0.7rem;">
                <span class="level-badge">
                    {stats.level_icon} Nível {stats.level_number} · 
                    {stats.level_name}
                </span>
                <div class="progress-wrap" style="margin-top: 0.45rem;">
                    <div class="progress-track">
                        <div class="progress-fill" style="width: {progress_pct}%;"></div>
                    </div>
                    <div class="progress-meta">
                        <span>{stats.xp} XP</span>
                        <span>{progress_pct}%</span>
                        <span>{next_label}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_main_menu(self) -> None:
        """Renderiza o menu principal."""
        st.markdown(
            """
            <div style="border-top: 1px solid var(--border);
                padding-top: 0.7rem; margin-bottom: 0.5rem;">
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        for item in MENU_ITEMS:
            self._render_menu_item(item)
    
    def _render_menu_item(self, item: MenuItem) -> None:
        """Renderiza item do menu."""
        try:
            is_active = self.current_page == item.key
            button_type = "primary" if is_active else "secondary"
            
            if st.button(
                f"{item.icon} {item.label}",
                use_container_width=True,
                type=button_type,
                key=f"nav_{item.key}",
            ):
                self._navegar_para_pagina(item.page)
        except Exception as e:
            logger.error(f"Erro ao renderizar menu item '{item.key}': {e}", exc_info=True)
    
    def _navegar_para_pagina(self, page: str) -> None:
        """Navega para página com tratamento de erros."""
        try:
            st.session_state.page = page
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para '{page}': {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")
    
    def _render_pilar_perfil(self) -> None:
        """Renderiza navegação contextual do pilar + perfil."""
        try:
            render_pilar_perfil(self.user, self.current_page)
        except Exception as e:
            logger.error(f"Erro ao renderizar pilar/perfil: {e}", exc_info=True)
    
    def _render_evolution_button(self) -> None:
        """Renderiza botão de evolução completa."""
        try:
            is_active = self.current_page == "evolution"
            button_type = "primary" if is_active else "secondary"
            
            if st.button(
                "📊 Evolução Completa",
                use_container_width=True,
                key="nav_evolution",
                type=button_type,
            ):
                self._navegar_para_pagina("evolution")
        except Exception as e:
            logger.error(f"Erro ao renderizar botão evolução: {e}", exc_info=True)
    
    def _render_share_button(self) -> None:
        """Renderiza botão de compartilhar conquista."""
        try:
            is_active = self.current_page == "share"
            button_type = "primary" if is_active else "secondary"
            
            if st.button(
                "📤 Compartilhar Conquista",
                use_container_width=True,
                key="nav_share",
                type=button_type,
            ):
                self._navegar_para_pagina("share")
        except Exception as e:
            logger.error(f"Erro ao renderizar botão compartilhar: {e}", exc_info=True)
    
    def _render_dark_mode_toggle(self) -> None:
        """Renderiza toggle de dark mode."""
        try:
            new_dark_mode = st.toggle(
                "🌙 Modo escuro",
                value=self.dark_mode,
                key="dark_mode_toggle",
            )
            
            if new_dark_mode != self.dark_mode:
                self._atualizar_dark_mode(new_dark_mode)
        except Exception as e:
            logger.error(f"Erro ao renderizar dark mode toggle: {e}", exc_info=True)
    
    def _atualizar_dark_mode(self, new_dark_mode: bool) -> None:
        """Atualiza configuração de dark mode."""
        try:
            # Atualiza no banco
            if self.db and hasattr(self.db, "update_user"):
                self.db.update_user({"dark_mode": new_dark_mode})
            
            # Atualiza no session state
            st.session_state.user["dark_mode"] = new_dark_mode
            
            # Limpa cache e rerun
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao atualizar dark mode: {e}", exc_info=True)
            st.error("❌ Erro ao alterar tema. Tente novamente.")
    
    def _render_logout_button(self) -> None:
        """Renderiza botão de sair."""
        try:
            if st.button(
                "🚪 Sair",
                use_container_width=True,
                key="nav_logout",
            ):
                _clear_session()
        except Exception as e:
            logger.error(f"Erro ao renderizar botão logout: {e}", exc_info=True)
    
    def _render_demo_badge(self) -> None:
        """Renderiza badge de modo demo."""
        try:
            if self.user.get("email") == config.DEMO_EMAIL:
                st.markdown(
                    """
                    <div style="background: var(--primary-light);
                        border: 1px solid var(--primary-border);
                        border-radius: 8px; padding: 0.35rem;
                        text-align: center; font-size: 0.74rem;
                        color: var(--primary); margin-top: 0.5rem;">
                        🎮 Modo Demo
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        except Exception as e:
            logger.debug(f"Erro ao renderizar demo badge: {e}")


# Função principal de compatibilidade
def render(services: Dict[str, Any]) -> None:
    """Função principal de renderização da sidebar."""
    renderer = SidebarRenderer(services)
    renderer.render()
