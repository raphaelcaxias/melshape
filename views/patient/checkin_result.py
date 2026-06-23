"""
Melshape — Resultado do Check-in.

Exibido após o check-in ser processado pelo Orchestrator.
Mostra XP ganho, badges, próximo passo e se a jornada avançou.
"""
import streamlit as st
from typing import Dict, Any, List
import logging

from services.orchestrator import OrchestratorResult
from views.components.cards import alert, metric_card

logger = logging.getLogger("Melshape.CheckinResult")


class CheckinResultRenderer:
    """Renderer para resultado do check-in."""
    
    def __init__(self, result: OrchestratorResult, user: Dict[str, Any]):
        self.result = result
        self.user = user
        self.nome = self._get_primeiro_nome()
    
    def _get_primeiro_nome(self) -> str:
        """Obtém primeiro nome do usuário de forma segura."""
        try:
            nome_completo = self.user.get("name", "")
            return nome_completo.split()[0] if nome_completo else "você"
        except Exception as e:
            logger.debug(f"Erro ao obter primeiro nome: {e}")
            return "você"
    
    def render(self) -> None:
        """Renderiza resultado completo."""
        # Card principal de sucesso
        self._render_success_header()
        
        # XP ganho
        self._render_xp()
        
        # Avanço na jornada
        self._render_jornada_avancada()
        
        # Badges novos
        self._render_novos_marcos()
        
        # Alertas do orchestrator
        self._render_alertas()
    
    def _render_success_header(self) -> None:
        """Renderiza cabeçalho de sucesso."""
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="border-color: var(--success);
                background: linear-gradient(135deg, var(--success-light), var(--surface));">
                <div style="font-size: 2.5rem; margin-bottom: 0.4rem;">🎉</div>
                <div style="font-weight: 800; font-size: 1.2rem; color: var(--success);">
                    Parabéns, {self.nome}!
                </div>
                <div style="font-size: 0.86rem; color: var(--text-muted); margin-top: 0.3rem;">
                    Seu check-in foi registrado com sucesso
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_xp(self) -> None:
        """Renderiza XP ganho."""
        xp = self._parse_xp()
        
        if xp > 0:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(
                    f"""
                    <div class="metric-card fade-in" style="border-color: var(--primary);">
                        <div style="font-size: 0.76rem; color: var(--text-muted);">
                            XP ganho
                        </div>
                        <div style="font-weight: 800; font-size: 1.8rem; color: var(--primary);">
                            +{xp}
                        </div>
                        <div style="font-size: 0.74rem; color: var(--text-muted);">
                            pontos de experiência
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            
            with col2:
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; justify-content: center;
                        height: 100%; font-size: 3rem;">
                        ⭐
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    
    def _parse_xp(self) -> int:
        """Obtém XP ganho de forma segura."""
        try:
            xp = self.result.xp_ganho
            return int(xp) if xp is not None else 0
        except (ValueError, TypeError, AttributeError):
            logger.warning("Erro ao obter XP ganho")
            return 0
    
    def _render_jornada_avancada(self) -> None:
        """Renderiza avanço na jornada."""
        # Verifica se há informações de jornada no resultado
        jornada_info = getattr(self.result, 'jornada_info', None)
        
        if not jornada_info:
            return
        
        etapa_atual = jornada_info.get("etapa_atual", "")
        proxima_etapa = jornada_info.get("proxima_etapa", "")
        progresso_pct = jornada_info.get("progresso_pct", 0)
        
        if not etapa_atual:
            return
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-top: 0.8rem;">
                <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.4rem;">
                    🗺️ Progresso na jornada
                </div>
                <div style="font-weight: 700; font-size: 1rem; color: var(--text);">
                    {etapa_atual}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Barra de progresso
        if progresso_pct > 0:
            st.markdown(
                f"""
                <div style="margin: 0.5rem 0;">
                    <div style="background: var(--surface-2); border-radius: 8px; 
                        height: 10px; overflow: hidden;">
                        <div style="background: linear-gradient(90deg, #8b5cf6, #a78bfa); 
                            height: 100%; width: {progresso_pct}%; border-radius: 8px; 
                            transition: width 0.5s ease;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; 
                        font-size: 0.72rem; color: var(--text-faint); margin-top: 0.3rem;">
                        <span>{progresso_pct}% concluído</span>
                        {f'<span>Próxima: {proxima_etapa}</span>' if proxima_etapa else ''}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def _render_novos_marcos(self) -> None:
        """Renderiza badges/marcos novos."""
        badges_novos = self._get_badges_novos()
        
        if not badges_novos:
            return
        
        st.markdown(
            """
            <div style="font-size: 0.86rem; font-weight: 700; color: var(--text);
                margin-top: 1rem; margin-bottom: 0.5rem;">
                🏆 Novas conquistas desbloqueadas!
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        for badge in badges_novos:
            self._render_badge_item(badge)
    
    def _get_badges_novos(self) -> List[Dict]:
        """Obtém lista de badges novos de forma segura."""
        try:
            badges = self.result.badges_novos
            return badges if isinstance(badges, list) else []
        except AttributeError:
            return []
    
    def _render_badge_item(self, badge: Dict) -> None:
        """Renderiza um item de badge."""
        nome = badge.get("name", badge.get("title", "Conquista"))
        descricao = badge.get("desc", badge.get("description", ""))
        xp = badge.get("xp", 0)
        
        xp_texto = f" · +{xp} XP" if xp > 0 else ""
        desc_html = (
            f'<div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.2rem;">'
            f'{descricao}</div>'
            if descricao else ""
        )
        
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 0.7rem;
                padding: 0.65rem 0.85rem; border: 2px solid var(--warning);
                border-radius: 12px; margin-bottom: 0.5rem;
                background: linear-gradient(135deg, var(--warning-light), var(--surface));">
                <span style="font-size: 1.5rem;">🏅</span>
                <div style="flex: 1;">
                    <div style="font-weight: 700; font-size: 0.92rem; color: var(--text);">
                        {nome}{xp_texto}
                    </div>
                    {desc_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_alertas(self) -> None:
        """Renderiza alertas do orchestrator."""
        alertas = self._get_alertas()
        
        if not alertas:
            return
        
        for kind, msg in alertas:
            alert(msg, kind)
    
    def _get_alertas(self) -> List[tuple]:
        """Obtém lista de alertas de forma segura."""
        try:
            alertas = self.result.alertas
            return alertas if isinstance(alertas, list) else []
        except AttributeError:
            return []


# Função principal de compatibilidade
def render_resultado(result: OrchestratorResult, user: Dict[str, Any]) -> None:
    """Renderiza resultado do check-in."""
    renderer = CheckinResultRenderer(result, user)
    renderer.render()
