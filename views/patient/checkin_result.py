"""
Melshape — Resultado do Check-in.

Exibido após o check-in ser processado pelo Orchestrator.
Mostra XP ganho, badges, próximo passo e se a jornada avançou.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Tuple
import logging

from services.orchestrator import OrchestratorResult
from views.components.cards import alert

logger = logging.getLogger("Melshape.CheckinResult")


class CheckinResultRenderer:
    """Renderer para resultado do check-in."""
    
    # Constantes de streak para mensagens motivacionais
    STREAK_LIMITE_LENDARIO = 30
    STREAK_LIMITE_FOGO = 7
    STREAK_LIMITE_HABITO = 3
    MAX_BADGES_EXIBIDAS = 3
    
    def __init__(self, result: OrchestratorResult, user: Dict[str, Any]):
        self.result = result
        self.user = user
        self.nome = self._get_primeiro_nome()
    
    def _get_primeiro_nome(self) -> str:
        """Obtém primeiro nome do usuário de forma segura."""
        try:
            nome_completo = self.user.get("name", "")
            return nome_completo.split()[0] if nome_completo else ""
        except Exception as e:
            logger.debug(f"Erro ao obter primeiro nome: {e}")
            return ""
    
    def render(self) -> None:
        """Renderiza resultado completo."""
        # XP ganho
        self._render_xp()
        
        # Avanço na jornada
        self._render_jornada_avancada()
        
        # Marcos novos
        self._render_novos_marcos()
        
        # Badges novas
        self._render_novas_badges()
        
        # Alertas
        self._render_alertas()
        
        # Próximo passo
        self._render_proximo_passo()
        
        # Mensagem motivacional
        self._render_mensagem_motivacional()
    
    def _render_xp(self) -> None:
        """Renderiza XP ganho."""
        xp = self._get_xp_ganho()
        
        if xp <= 0:
            return
        
        st.markdown(
            f"""
            <div style="background: var(--primary-light);
                border: 1px solid var(--primary-border);
                border-radius: 16px; padding: 1.2rem;
                text-align: center; margin-bottom: 0.8rem;">
                <div style="font-size: 2.2rem; font-weight: 800;
                    color: var(--primary);">+{xp} XP</div>
                <div style="font-size: 0.84rem; color: var(--text-muted);
                    margin-top: 0.3rem;">
                    Ganhos com o check-in de hoje
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_xp_ganho(self) -> int:
        """Obtém XP ganho de forma segura."""
        try:
            xp = getattr(self.result, "xp_ganho", 0)
            return int(xp) if xp is not None else 0
        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao obter XP ganho: {e}")
            return 0
    
    def _render_jornada_avancada(self) -> None:
        """Renderiza avanço na jornada."""
        try:
            if not getattr(self.result, "jornada_avancou", False):
                return
        except Exception as e:
            logger.debug(f"Erro ao verificar jornada: {e}")
            return
        
        st.markdown(
            """
            <div class="alert-success" style="margin-bottom: 0.6rem;">
                🗺️ Você avançou para a próxima etapa da sua jornada!
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_novos_marcos(self) -> None:
        """Renderiza novos marcos alcançados."""
        marcos = self._get_marcos_novos()
        
        if not marcos:
            return
        
        for marco in marcos:
            st.markdown(
                f"""
                <div class="alert-success" style="margin-bottom: 0.4rem;">
                    🏁 {marco}
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def _get_marcos_novos(self) -> List[str]:
        """Obtém lista de marcos novos de forma segura."""
        try:
            marcos = getattr(self.result, "marcos_novos", [])
            return marcos if isinstance(marcos, list) else []
        except Exception as e:
            logger.warning(f"Erro ao obter marcos novos: {e}")
            return []
    
    def _render_novas_badges(self) -> None:
        """Renderiza novas badges."""
        badges_visuais = self._get_badges_visuais()
        
        if not badges_visuais:
            return
        
        st.markdown('<div style="margin: 0.6rem 0;">', unsafe_allow_html=True)
        
        for badge in badges_visuais[:self.MAX_BADGES_EXIBIDAS]:
            self._render_badge_item(badge)
        
        # Indicador de mais badges
        total = len(badges_visuais)
        if total > self.MAX_BADGES_EXIBIDAS:
            st.markdown(
                f"""
                <div style="font-size: 0.76rem; color: var(--text-muted);
                    text-align: center; margin-top: 0.4rem;">
                    +{total - self.MAX_BADGES_EXIBIDAS} outra(s) conquista(s)
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def _get_badges_visuais(self) -> List[str]:
        """Obtém badges visuais (excluindo marcos) de forma segura."""
        try:
            badges_novos = getattr(self.result, "badges_novos", [])
            marcos_novos = getattr(self.result, "marcos_novos", [])
            
            if not isinstance(badges_novos, list):
                return []
            
            marcos_set = set(marcos_novos) if isinstance(marcos_novos, list) else set()
            return [b for b in badges_novos if b not in marcos_set]
        except Exception as e:
            logger.warning(f"Erro ao obter badges visuais: {e}")
            return []
    
    def _render_badge_item(self, badge: str) -> None:
        """Renderiza um item de badge."""
        st.markdown(
            f"""
            <div style="background: var(--primary-light);
                border: 1px solid var(--primary-border);
                border-radius: 12px; padding: 0.6rem 0.9rem;
                margin-bottom: 0.4rem; font-size: 0.9rem;
                font-weight: 600; color: var(--text);">
                🏅 {badge}
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_alertas(self) -> None:
        """Renderiza alertas."""
        alertas = self._get_alertas()
        
        if not alertas:
            return
        
        for kind, msg in alertas:
            alert(msg, kind)
    
    def _get_alertas(self) -> List[Tuple[str, str]]:
        """Obtém lista de alertas de forma segura."""
        try:
            alertas = getattr(self.result, "alertas", [])
            return alertas if isinstance(alertas, list) else []
        except Exception as e:
            logger.warning(f"Erro ao obter alertas: {e}")
            return []
    
    def _render_proximo_passo(self) -> None:
        """Renderiza próximo passo."""
        proximo = self._get_proximo_passo()
        
        if not proximo:
            return
        
        st.markdown(
            f"""
            <div style="margin-top: 1rem; padding: 0.9rem;
                background: var(--surface-2); border-radius: 12px;">
                <div style="font-size: 0.74rem; font-weight: 700;
                    letter-spacing: 0.06em; color: var(--text-faint);
                    text-transform: uppercase; margin-bottom: 0.4rem;">
                    Próximo passo
                </div>
                <div style="font-size: 0.94rem; font-weight: 600;
                    color: var(--text);">{proximo}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Botão CTA se houver hub de destino
        self._render_cta_button()
    
    def _get_proximo_passo(self) -> Optional[str]:
        """Obtém próximo passo de forma segura."""
        try:
            passo = getattr(self.result, "proximo_passo", None)
            return passo if passo else None
        except Exception as e:
            logger.debug(f"Erro ao obter próximo passo: {e}")
            return None
    
    def _render_cta_button(self) -> None:
        """Renderiza botão CTA para próximo hub."""
        try:
            proximo_hub = getattr(self.result, "proximo_hub", None)
            if not proximo_hub:
                return
        except Exception as e:
            logger.debug(f"Erro ao verificar próximo hub: {e}")
            return
        
        if st.button(
            "Fazer agora →",
            type="primary",
            use_container_width=True,
            key="ci_result_cta",
        ):
            self._navegar_para_proximo_hub()
    
    def _navegar_para_proximo_hub(self) -> None:
        """Navega para o próximo hub configurado."""
        try:
            st.session_state.page = getattr(self.result, "proximo_hub", None)
            st.session_state.hub_tipo = getattr(self.result, "proximo_tipo", None)
            st.session_state.pop("ci_result", None)
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para próximo hub: {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")
    
    def _render_mensagem_motivacional(self) -> None:
        """Renderiza mensagem motivacional baseada na streak."""
        streak = self._get_streak()
        
        if streak <= 0:
            return
        
        if streak >= self.STREAK_LIMITE_LENDARIO:
            self._quote("🏆 30 dias. Isso já é mais do que a maioria das pessoas faz na vida.")
        elif streak >= self.STREAK_LIMITE_FOGO:
            self._quote(f"🔥 {streak} dias seguidos. A consistência está virando parte de você.")
        elif streak >= self.STREAK_LIMITE_HABITO:
            self._quote(f"⚡ {streak} dias. O hábito está começando a se formar.")
        elif streak == 1:
            self._quote("🌱 O primeiro passo de volta. Amanhã será mais fácil.")
        else:
            # Fallback para streaks entre 2 e 2 (não cobertos acima)
            self._quote(f"💪 {streak} dias. Continue assim!")
    
    def _get_streak(self) -> int:
        """Obtém streak de forma segura."""
        try:
            streak = getattr(self.result, "streak", 0)
            return int(streak) if streak is not None else 0
        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao obter streak: {e}")
            return 0
    
    def _quote(self, text: str) -> None:
        """Renderiza uma citação motivacional."""
        st.markdown(
            f"""
            <div style="font-style: italic; font-size: 0.86rem;
                color: var(--text-muted); padding: 0.7rem 0.9rem;
                border-left: 3px solid var(--primary);
                margin-top: 1rem; background: var(--surface-2);
                border-radius: 0 8px 8px 0;">{text}</div>
            """,
            unsafe_allow_html=True,
        )


# Função de compatibilidade
def render_resultado(result: OrchestratorResult, user: Dict[str, Any]) -> None:
    """Renderiza resultado do check-in (compatibilidade)."""
    renderer = CheckinResultRenderer(result, user)
    renderer.render()
