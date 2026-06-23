"""
Melshape — Jornada: blocos de etapa atual e próximo passo.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
import logging

from services.journey_service import JourneyService

logger = logging.getLogger("Melshape.JourneyBlocks")


# Constantes de limiares de progresso
PROGRESSO_ETAPA_DESTAQUE = 80
PROGRESSO_ETAPA_ALERTA = 40
PROGRESSO_ETAPA_COMPLETO = 100

# Constantes de urgência
URGENCIA_MAP = {
    "alta": ("error", "🚨"),
    "media": ("warning", "⚡"),
    "baixa": ("info", "💡"),
    "ok": ("success", "✅"),
}

# Fallbacks
DEFAULT_ICONE_ETAPA = "📍"
DEFAULT_ICONE_PASSO = "➡️"
DEFAULT_ACAO_PASSO = "Continue sua jornada"


class JourneyBlocksRenderer:
    """Renderer para blocos da jornada."""
    
    def __init__(self, svc: Optional[JourneyService], user: Dict[str, Any]):
        self.svc = svc
        self.user = user or {}
    
    def render_etapa_atual(self, progresso: Dict[str, Any]) -> None:
        """Renderiza etapa atual."""
        self._render_header_bloco("Etapa Atual")
        
        # Extrai dados de forma segura
        etapa = self._extrair_etapa_atual(progresso)
        pct = self._parse_int(progresso.get("pct_etapa", 0))
        ordem = self._parse_int(etapa.get("ordem", 1))
        total = self._parse_int(progresso.get("total", 1))
        
        # Renderiza card principal
        self._render_card_etapa_atual(etapa, pct, ordem, total)
        
        # Renderiza critérios
        criterios = etapa.get("criterios", [])
        if criterios:
            self._render_criterios_etapa(criterios)
    
    def _render_header_bloco(self, titulo: str) -> None:
        """Renderiza cabeçalho de bloco."""
        st.markdown(
            f"""
            <p style="font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em;
                color: var(--text-faint); text-transform: uppercase;
                margin-bottom: 0.7rem;">
                {titulo}
            </p>
            """,
            unsafe_allow_html=True,
        )
    
    def _extrair_etapa_atual(self, progresso: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai etapa atual de forma segura."""
        try:
            etapa = progresso.get("etapa_atual", {})
            return etapa if isinstance(etapa, dict) else {}
        except Exception as e:
            logger.error(f"Erro ao extrair etapa atual: {e}", exc_info=True)
            return {}
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _render_card_etapa_atual(
        self,
        etapa: Dict[str, Any],
        pct: int,
        ordem: int,
        total: int,
    ) -> None:
        """Renderiza card da etapa atual."""
        icone = etapa.get("icone", DEFAULT_ICONE_ETAPA)
        nome = etapa.get("nome", "—")
        descricao = etapa.get("descricao", "")
        cor = self._get_cor_progresso_etapa(pct)
        status_texto = self._get_status_texto_etapa(pct)
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="display: flex; align-items: center; gap: 0.7rem;
                    margin-bottom: 0.6rem;">
                    <span style="font-size: 2.2rem;">{icone}</span>
                    <div>
                        <div style="font-weight: 800; font-size: 1.05rem; color: var(--text);">
                            Etapa {ordem} de {total}
                        </div>
                        <div style="font-size: 0.88rem; color: var(--primary); font-weight: 600; margin-top: 0.15rem;">
                            {nome}
                        </div>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.7rem;">
                    {descricao}
                </div>
                <div class="progress-track">
                    <div class="progress-fill {cor}" style="width: {pct}%;"></div>
                </div>
                <div class="progress-meta">
                    <span>Progresso da etapa</span>
                    <span>{pct}%</span>
                    <span>{status_texto}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_cor_progresso_etapa(self, pct: int) -> str:
        """Retorna cor baseada no progresso da etapa."""
        if pct >= PROGRESSO_ETAPA_DESTAQUE:
            return "success"
        elif pct >= PROGRESSO_ETAPA_ALERTA:
            return "warning"
        return ""
    
    def _get_status_texto_etapa(self, pct: int) -> str:
        """Retorna texto de status baseado no progresso."""
        return "✅ Pronto para avançar!" if pct >= PROGRESSO_ETAPA_COMPLETO else ""
    
    def _render_criterios_etapa(self, criterios: List[str]) -> None:
        """Renderiza critérios da etapa."""
        st.markdown(
            """
            <div style="font-size: 0.80rem; color: var(--text-muted);
                margin-top: 0.5rem; font-weight: 600;">
                Critérios:
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        for criterio in criterios:
            st.markdown(
                f"""
                <div style="font-size: 0.82rem; color: var(--text-muted); padding: 0.2rem 0;">
                    • {criterio}
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def render_proximo_passo(self, progresso: Dict[str, Any]) -> None:
        """Renderiza próximo passo com tratamento de erros."""
        self._render_header_bloco("Próximo Passo")
        
        # Obtém próximo passo com tratamento de erros
        passo = self._get_proximo_passo(progresso)
        
        if not passo:
            self._render_erro_proximo_passo()
            return
        
        # Renderiza card do próximo passo
        self._render_card_proximo_passo(passo)
        
        # Renderiza botão de ação
        self._render_botao_proximo_passo(passo)
        
        # Renderiza preview da próxima etapa
        etapa_seguinte = progresso.get("etapa_seguinte")
        if etapa_seguinte:
            self._render_preview_proxima_etapa(etapa_seguinte)
    
    def _get_proximo_passo(self, progresso: Dict[str, Any]) -> Optional[Dict]:
        """Obtém próximo passo com tratamento de erros."""
        if not self.svc:
            logger.error("JourneyService não disponível")
            return None
        
        try:
            etapa = self._extrair_etapa_atual(progresso)
            passo = self.svc.proximo_passo(etapa, self.user)
            
            if not isinstance(passo, dict):
                logger.error("Próximo passo não é um dict válido")
                return None
            
            return passo
        except Exception as e:
            logger.error(f"Erro ao obter próximo passo: {e}", exc_info=True)
            return None
    
    def _render_erro_proximo_passo(self) -> None:
        """Renderiza mensagem de erro quando próximo passo não está disponível."""
        st.markdown(
            """
            <div class="metric-card fade-in" style="text-align: center;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">⚠️</div>
                <div style="font-size: 0.88rem; color: var(--text-muted);">
                    Não foi possível determinar o próximo passo.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_card_proximo_passo(self, passo: Dict) -> None:
        """Renderiza card do próximo passo."""
        icone = passo.get("icone", DEFAULT_ICONE_PASSO)
        acao = passo.get("acao", DEFAULT_ACAO_PASSO)
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="font-size: 2.2rem; margin-bottom: 0.6rem;">
                    {icone}
                </div>
                <div style="font-weight: 700; font-size: 0.98rem; color: var(--text);">
                    {acao}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_botao_proximo_passo(self, passo: Dict) -> None:
        """Renderiza botão de ação do próximo passo."""
        pagina = passo.get("pagina")
        
        if not pagina:
            return
        
        try:
            icone = passo.get("icone", DEFAULT_ICONE_PASSO)
            
            if st.button(
                f"{icone} Fazer agora →",
                type="primary",
                use_container_width=True,
                key="jrn_proximo_passo",
            ):
                self._navegar_para_pagina(passo)
        except Exception as e:
            logger.error(f"Erro ao renderizar botão de próximo passo: {e}", exc_info=True)
    
    def _navegar_para_pagina(self, passo: Dict) -> None:
        """Navega para a página do próximo passo."""
        try:
            pagina = passo.get("pagina")
            hub_tipo = passo.get("hub_tipo", "")
            
            st.session_state.page = pagina
            
            if hub_tipo:
                st.session_state.hub_tipo = hub_tipo
            
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para página: {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")
    
    def _render_preview_proxima_etapa(self, etapa_seguinte: Dict) -> None:
        """Renderiza preview da próxima etapa."""
        try:
            icone = etapa_seguinte.get("icone", "")
            nome = etapa_seguinte.get("nome", "")
            descricao = etapa_seguinte.get("descricao", "")
            
            st.markdown(
                f"""
                <div style="margin-top: 0.9rem; padding: 0.7rem 0.9rem;
                    background: var(--surface-2); border-radius: 10px;
                    font-size: 0.82rem;">
                    <div style="color: var(--text-faint); font-size: 0.74rem;
                        margin-bottom: 0.25rem;">A seguir:</div>
                    <div style="font-weight: 600; color: var(--text); font-size: 0.88rem;">
                        {icone} {nome}
                    </div>
                    <div style="color: var(--text-muted); font-size: 0.80rem; margin-top: 0.2rem;">
                        {descricao}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar preview da próxima etapa: {e}", exc_info=True)


# Funções de compatibilidade
def _bloco_etapa_atual(progresso: Dict[str, Any]) -> None:
    """Renderiza etapa atual (compatibilidade)."""
    renderer = JourneyBlocksRenderer(None, {})
    renderer.render_etapa_atual(progresso)


def _bloco_proximo_passo(svc: Optional[JourneyService], progresso: Dict[str, Any],
                          user: Dict[str, Any]) -> None:
    """Renderiza próximo passo (compatibilidade)."""
    renderer = JourneyBlocksRenderer(svc, user)
    renderer.render_proximo_passo(progresso)
