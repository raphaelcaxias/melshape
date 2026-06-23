"""
Melshape — Next Step: renderização do card.
"""
import streamlit as st
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger("Melshape.NextStepRender")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Mapeamento de urgência para cores
URGENCY_COLORS = {
    "alta": "var(--error)",
    "media": "var(--warning)",
    "baixa": "var(--info)",
    "ok": "var(--success)",
}

# Fallbacks
DEFAULT_ICON = "⭐"
DEFAULT_TEXT = "Continue sua jornada"
DEFAULT_URGENCY = "ok"
DEFAULT_COLOR = "var(--border)"


@dataclass
class NextStepRenderData:
    """Dados para renderização do próximo passo."""
    icon: str = DEFAULT_ICON
    text: str = DEFAULT_TEXT
    urgency: str = DEFAULT_URGENCY
    page: Optional[str] = None
    hub_tipo: Optional[str] = None
    marco_title: Optional[str] = None
    professional: Optional[str] = None


class NextStepRenderRenderer:
    """Renderer dedicado para o card de próximo passo."""
    
    def render(self, data: NextStepRenderData) -> None:
        """Renderiza o card de próximo passo com tratamento de erros."""
        try:
            color = self._get_urgency_color(data.urgency)
            
            # HTML do marco
            marco_html = self._build_marco_html(data.marco_title)
            
            # HTML do profissional
            pro_html = self._build_professional_html(data.professional)
            
            # Renderiza card
            self._render_card_html(data, color, marco_html, pro_html)
            
            # Botão de ação
            if data.page:
                self._render_action_button(data)
        except Exception as e:
            logger.error(f"Erro ao renderizar card de próximo passo: {e}", exc_info=True)
            self._render_card_minimo()
    
    def _get_urgency_color(self, urgency: str) -> str:
        """Obtém cor baseada na urgência."""
        try:
            return URGENCY_COLORS.get(urgency, DEFAULT_COLOR)
        except Exception as e:
            logger.debug(f"Erro ao obter cor de urgência: {e}")
            return DEFAULT_COLOR
    
    def _build_marco_html(self, marco_title: Optional[str]) -> str:
        """Constrói HTML do marco."""
        try:
            if not marco_title:
                return ""
            
            return (
                f'<span style="font-size: 0.76rem; color: var(--primary);'
                f'background: var(--primary-light); padding: 0.18rem 0.65rem;'
                f'border-radius: 9999px; border: 1px solid var(--primary-border);'
                f'white-space: nowrap;">→ {marco_title}</span>'
            )
        except Exception as e:
            logger.debug(f"Erro ao construir HTML do marco: {e}")
            return ""
    
    def _build_professional_html(self, professional: Optional[str]) -> str:
        """Constrói HTML do profissional."""
        try:
            if not professional:
                return ""
            
            return (
                f'<span style="font-size: 0.78rem; color: var(--text-muted);">'
                f'👤 {professional}</span>'
            )
        except Exception as e:
            logger.debug(f"Erro ao construir HTML do profissional: {e}")
            return ""
    
    def _render_card_html(
        self,
        data: NextStepRenderData,
        color: str,
        marco_html: str,
        pro_html: str,
    ) -> None:
        """Renderiza HTML do card."""
        try:
            st.markdown(
                f"""
                <div class="fade-in" style="background: var(--surface-2);
                    border-radius: 16px; padding: 0.85rem 1.1rem;
                    margin-bottom: 1.1rem; border: 1px solid var(--border);
                    border-left: 4px solid {color};">
                    <div style="display: flex; align-items: center;
                        justify-content: space-between; flex-wrap: wrap; gap: 0.6rem;">
                        <div style="display: flex; align-items: center; gap: 0.7rem;">
                            <span style="font-size: 1.5rem;">{data.icon}</span>
                            <div>
                                <div style="font-size: 0.72rem; color: var(--text-faint);
                                    font-weight: 700; text-transform: uppercase;
                                    letter-spacing: 0.06em;">
                                    Próximo passo
                                </div>
                                <div style="font-weight: 700; font-size: 0.94rem;
                                    color: var(--text);">
                                    {data.text}
                                </div>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.7rem;
                            flex-wrap: wrap;">
                            {pro_html}
                            {marco_html}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar HTML do card: {e}", exc_info=True)
    
    def _render_action_button(self, data: NextStepRenderData) -> None:
        """Renderiza botão de ação."""
        try:
            if st.button(
                f'{data.icon} Fazer agora',
                type="primary",
                use_container_width=True,
                key="next_step_cta",
            ):
                self._navegar_para_pagina(data.page, data.hub_tipo)
        except Exception as e:
            logger.error(f"Erro ao renderizar botão de ação: {e}", exc_info=True)
    
    def _navegar_para_pagina(self, page: str, hub_tipo: Optional[str]) -> None:
        """Navega para página com tratamento de erros."""
        try:
            st.session_state.page = page
            
            if hub_tipo:
                st.session_state.hub_tipo = hub_tipo
            
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para '{page}': {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")
    
    def _render_card_minimo(self) -> None:
        """Renderiza card mínimo em caso de erro."""
        try:
            st.markdown(
                """
                <div class="fade-in" style="background: var(--surface-2);
                    border-radius: 16px; padding: 0.85rem 1.1rem;
                    margin-bottom: 1.1rem; border: 1px solid var(--border);
                    border-left: 4px solid var(--success);">
                    <div style="display: flex; align-items: center; gap: 0.7rem;">
                        <span style="font-size: 1.5rem;">⭐</span>
                        <div style="font-weight: 700; font-size: 0.94rem; color: var(--text);">
                            Continue sua jornada
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar card mínimo: {e}", exc_info=True)


# Função de compatibilidade
def _render_card(
    acao: Dict[str, Any],
    marco: Optional[Dict[str, str]],
    profissional: Optional[str],
) -> None:
    """Renderiza o card de próximo passo (compatibilidade)."""
    try:
        data = NextStepRenderData(
            icon=acao.get("icone", DEFAULT_ICON),
            text=acao.get("texto", DEFAULT_TEXT),
            urgency=acao.get("urgencia", DEFAULT_URGENCY),
            page=acao.get("pagina"),
            hub_tipo=acao.get("hub_tipo"),
            marco_title=marco.get("titulo") if marco else None,
            professional=profissional,
        )
        
        renderer = NextStepRenderRenderer()
        renderer.render(data)
    except Exception as e:
        logger.error(f"Erro ao renderizar card de compatibilidade: {e}", exc_info=True)
