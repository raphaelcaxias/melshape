"""
Melshape — Sidebar: navegação contextual por pilar e logout.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger("Melshape.SidebarNav")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Pilares específicos com suas rotas
PILAR_MAP = {
    "glp1": {
        "icon": "💉",
        "label": "GLP-1",
        "route": "glp1",
    },
    "bariatric": {
        "icon": "🔪",
        "label": "Bariátrica",
        "route": "bariatric",
    },
    "fitness": {
        "icon": "💪",
        "label": "Fitness",
        "route": "dashboard",
    },
}

# Chaves de sessão a serem limpas no logout
SESSION_KEYS_TO_CLEAR = [
    "user",
    "professional",
    "perfil_id",
    "demo_loaded",
    "onboarding_step",
    "onboarding_mode",
    "pro_page",
    "pro_selected_patient",
    "ci_result",
]

# Fallbacks
DEFAULT_PAGE = "home"
DEFAULT_HEALTH_MODE = "general"
DEFAULT_USER = {}
LANDING_PAGE = "landing"


class SidebarNavRenderer:
    """Renderer dedicado para navegação contextual da sidebar."""
    
    def __init__(self):
        self.user = self._get_user()
        self.current_page = self._get_current_page()
        self.health_mode = self._get_health_mode()
    
    def _get_user(self) -> Dict[str, Any]:
        """Obtém usuário do session state de forma segura."""
        try:
            return st.session_state.get("user", DEFAULT_USER)
        except Exception as e:
            logger.error(f"Erro ao obter usuário: {e}")
            return DEFAULT_USER
    
    def _get_current_page(self) -> str:
        """Obtém página atual de forma segura."""
        try:
            return st.session_state.get("page", DEFAULT_PAGE)
        except Exception as e:
            logger.error(f"Erro ao obter página atual: {e}")
            return DEFAULT_PAGE
    
    def _get_health_mode(self) -> str:
        """Obtém modo de saúde do usuário."""
        try:
            return self.user.get("health_mode", DEFAULT_HEALTH_MODE)
        except Exception as e:
            logger.debug(f"Erro ao obter health mode: {e}")
            return DEFAULT_HEALTH_MODE
    
    def render(self) -> None:
        """Renderiza navegação contextual com tratamento de erros."""
        try:
            # Navegação do pilar
            self._render_pilar_nav()
            
            # Perfil
            self._render_profile_button()
            
            # Divisor
            self._render_divider()
        except Exception as e:
            logger.error(f"Erro ao renderizar navegação contextual: {e}", exc_info=True)
    
    def _render_pilar_nav(self) -> None:
        """Renderiza botão de navegação do pilar específico."""
        if self.health_mode not in PILAR_MAP:
            return
        
        try:
            pilar = PILAR_MAP[self.health_mode]
            is_active = self.current_page == pilar["route"]
            button_type = "primary" if is_active else "secondary"
            
            if st.button(
                f"{pilar['icon']} {pilar['label']}",
                use_container_width=True,
                type=button_type,
                key="nav_pilar",
            ):
                self._navegar_para_pagina(pilar["route"])
        except Exception as e:
            logger.error(f"Erro ao renderizar navegação do pilar: {e}", exc_info=True)
    
    def _render_profile_button(self) -> None:
        """Renderiza botão de perfil."""
        try:
            is_active = self.current_page == "profile"
            button_type = "primary" if is_active else "secondary"
            
            if st.button(
                "👤 Perfil",
                use_container_width=True,
                key="nav_profile",
                type=button_type,
            ):
                self._navegar_para_pagina("profile")
        except Exception as e:
            logger.error(f"Erro ao renderizar botão perfil: {e}", exc_info=True)
    
    def _navegar_para_pagina(self, page: str) -> None:
        """Navega para página com tratamento de erros."""
        try:
            st.session_state.page = page
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para '{page}': {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")
    
    def _render_divider(self) -> None:
        """Renderiza divisor visual."""
        try:
            st.markdown(
                """
                <div style="border-top: 1px solid var(--border);
                    margin: 0.5rem 0;">
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.debug(f"Erro ao renderizar divisor: {e}")


def render_pilar_perfil(user: Dict[str, Any], current_page: str) -> None:
    """
    Renderiza link do pilar específico + perfil + sair.
    
    Mantido para compatibilidade com a interface original.
    """
    try:
        renderer = SidebarNavRenderer()
        renderer.render()
    except Exception as e:
        logger.error(f"Erro ao renderizar pilar/perfil: {e}", exc_info=True)


def _clear_session() -> None:
    """
    Limpa os dados da sessão e redireciona para landing.
    
    Mantido para compatibilidade com a interface original.
    """
    try:
        # Limpa chaves específicas
        for key in SESSION_KEYS_TO_CLEAR:
            try:
                st.session_state.pop(key, None)
            except Exception as e:
                logger.debug(f"Erro ao limpar chave '{key}': {e}")
        
        # Redireciona para landing
        st.session_state.page = LANDING_PAGE
        st.rerun()
    except Exception as e:
        logger.error(f"Erro ao limpar sessão: {e}", exc_info=True)
        # Fallback: tenta redirecionar mesmo com erro
        try:
            st.session_state.page = LANDING_PAGE
            st.rerun()
        except Exception as e2:
            logger.error(f"Erro no fallback de logout: {e2}", exc_info=True)
            st.error("❌ Erro ao sair. Por favor, recarregue a página.")
