"""
Melshape — Tela de Jornada do Paciente.

O paciente vê:
1. Em qual etapa da jornada está
2. O que já conquistou (marcos)
3. O próximo passo concreto e acionável
4. Linha do tempo de eventos
"""
import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

from services.journey_service import JourneyService
from views.components.cards import (
    section_header, empty_state, alert,
    show_new_achievements, metric_card,
)
from views.patient.journey_timeline import (
    _tab_todas_etapas,
    render_linha_do_tempo, render_marcos,
)

logger = logging.getLogger("Melshape.Journey")


# Constantes de modos de saúde
MODE_LABELS = {
    "general": ("⚖️", "Emagrecimento", "general"),
    "fitness": ("💪", "Fitness", "fitness"),
    "bariatric": ("🔪", "Pós-Bariátrica", "bariatric"),
    "glp1": ("💉", "GLP-1", "glp1"),
}

# Fallbacks
DEFAULT_ICON = "⚖️"
DEFAULT_LABEL = "Geral"
DEFAULT_MODE = "general"
DEFAULT_NOME_JORNADA = "Minha Jornada"


@dataclass
class JourneyProgress:
    """Progresso da jornada."""
    pct_geral: int = 0
    total: int = 0
    concluidas: List[Dict] = field(default_factory=list)
    pendentes: List[Dict] = field(default_factory=list)
    etapa_atual: Dict[str, Any] = field(default_factory=dict)
    etapa_seguinte: Optional[Dict[str, Any]] = None
    pct_etapa: int = 0


class JourneyRenderer:
    """Renderer dedicado para tela de jornada."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.svc = self._init_journey_service()
        self.health_mode = user.get("health_mode", DEFAULT_MODE)
        self.icon_hm, self.label_hm, _ = self._get_mode_info()
    
    def _init_journey_service(self) -> Optional[JourneyService]:
        """Inicializa JourneyService com tratamento de erros."""
        if not self.db:
            logger.error("Database não disponível para JourneyRenderer")
            return None
        
        try:
            return JourneyService(self.db)
        except Exception as e:
            logger.error(f"Erro ao inicializar JourneyService: {e}", exc_info=True)
            return None
    
    def _get_mode_info(self) -> tuple:
        """Obtém informações do modo de saúde com fallback."""
        try:
            return MODE_LABELS.get(
                self.health_mode,
                (DEFAULT_ICON, DEFAULT_LABEL, DEFAULT_MODE)
            )
        except Exception as e:
            logger.debug(f"Erro ao obter info do modo: {e}")
            return (DEFAULT_ICON, DEFAULT_LABEL, DEFAULT_MODE)
    
    def render(self) -> None:
        """Renderiza tela de jornada."""
        section_header(
            f"{self.icon_hm} Sua Jornada",
            f"Jornada {self.label_hm} — cada etapa é uma transformação real",
        )
        
        # Verifica se serviço foi inicializado
        if not self.svc:
            self._render_error_state()
            return
        
        # Garante que jornada existe
        jornada = self._garantir_jornada()
        
        if not jornada:
            self._render_jornada_nao_encontrada()
            return
        
        jornada_id = jornada.get("id", "")
        progresso = self._get_progresso(jornada_id)
        
        # Verifica marcos automáticos
        self._verificar_marcos(jornada_id)
        
        # Bloco de progresso geral
        self._render_progresso_geral(progresso, jornada)
        
        st.divider()
        
        # Etapa atual + próximo passo
        self._render_etapa_e_proximo_passo(progresso)
        
        st.divider()
        
        # Tabs
        self._render_tabs(progresso, jornada_id)
    
    def _render_error_state(self) -> None:
        """Renderiza estado de erro quando serviço não está disponível."""
        alert(
            "❌ Não foi possível carregar o módulo de jornada. "
            "Por favor, recarregue a página ou entre em contato com o suporte.",
            "error",
        )
    
    def _garantir_jornada(self) -> Optional[Dict]:
        """Garante que jornada existe com tratamento de erros."""
        try:
            jornada = self.svc.garantir_jornada(self.user)
            return jornada if jornada else None
        except Exception as e:
            logger.error(f"Erro ao garantir jornada: {e}", exc_info=True)
            return None
    
    def _render_jornada_nao_encontrada(self) -> None:
        """Renderiza mensagem quando jornada não é encontrada."""
        empty_state(
            "🗺️",
            "Não foi possível carregar sua jornada",
            "Tente recarregar a página",
        )
    
    @st.cache_data(ttl=60)
    def _get_progresso(_self, jornada_id: str) -> JourneyProgress:
        """Obtém progresso da jornada (com cache)."""
        try:
            raw = _self.svc.progresso_jornada(jornada_id, _self.health_mode)
            
            return JourneyProgress(
                pct_geral=_self._parse_int(raw.get("pct_geral", 0)),
                total=_self._parse_int(raw.get("total", 0)),
                concluidas=raw.get("concluidas", []),
                pendentes=raw.get("pendentes", []),
                etapa_atual=raw.get("etapa_atual", {}),
                etapa_seguinte=raw.get("etapa_seguinte"),
                pct_etapa=_self._parse_int(raw.get("pct_etapa", 0)),
            )
        except Exception as e:
            logger.error(f"Erro ao obter progresso da jornada: {e}", exc_info=True)
            return JourneyProgress()
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _verificar_marcos(self, jornada_id: str) -> None:
        """Verifica e exibe novos marcos com tratamento de erros."""
        try:
            novos_marcos = self.svc.verificar_marcos_automaticos(jornada_id, self.user)
            
            if not isinstance(novos_marcos, list):
                return
            
            for marco in novos_marcos:
                st.toast(f"🏁 Marco alcançado: {marco}", icon="🎉")
        except Exception as e:
            logger.error(f"Erro ao verificar marcos: {e}", exc_info=True)
    
    def _render_progresso_geral(self, progresso: JourneyProgress,
                                  jornada: Dict) -> None:
        """Renderiza progresso geral da jornada."""
        nome_jornada = jornada.get("nome", DEFAULT_NOME_JORNADA)
        inicio_str = self._formatar_data_inicio(jornada.get("iniciada_em", ""))
        
        concluidas = len(progresso.concluidas)
        total = progresso.total
        pct = progresso.pct_geral
        
        self._render_card_progresso_geral(
            nome_jornada, inicio_str, concluidas, total, pct
        )
    
    def _formatar_data_inicio(self, iniciada_em: str) -> str:
        """Formata data de início da jornada."""
        try:
            return iniciada_em[:10] if iniciada_em else "—"
        except Exception as e:
            logger.debug(f"Erro ao formatar data de início: {e}")
            return "—"
    
    def _render_card_progresso_geral(
        self,
        nome_jornada: str,
        inicio_str: str,
        concluidas: int,
        total: int,
        pct: int,
    ) -> None:
        """Renderiza card de progresso geral."""
        restantes = max(0, total - concluidas)
        status_texto = "🏆 Completo!" if pct == 100 else f"{restantes} etapas restantes"
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="display: flex; justify-content: space-between;
                    align-items: flex-start; margin-bottom: 0.7rem;">
                    <div>
                        <div style="font-weight: 800; font-size: 1.08rem; color: var(--text);">
                            {nome_jornada}
                        </div>
                        <div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.2rem;">
                            Iniciada em {inicio_str}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.7rem; font-weight: 800; color: var(--primary);">
                            {concluidas}/{total}
                        </div>
                        <div style="font-size: 0.76rem; color: var(--text-muted);">etapas</div>
                    </div>
                </div>
                <div class="progress-track">
                    <div class="progress-fill" style="width: {pct}%;"></div>
                </div>
                <div class="progress-meta">
                    <span>Progresso geral</span>
                    <span>{pct}%</span>
                    <span>{status_texto}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_etapa_e_proximo_passo(self, progresso: JourneyProgress) -> None:
        """Renderiza etapa atual e próximo passo em colunas."""
        col_etapa, col_proximo = st.columns([3, 2])
        
        with col_etapa:
            self._render_etapa_atual(progresso)
        
        with col_proximo:
            self._render_proximo_passo(progresso)
    
    def _render_etapa_atual(self, progresso: JourneyProgress) -> None:
        """Renderiza etapa atual com tratamento de erros."""
        try:
            from views.patient.journey_blocks import _bloco_etapa_atual
            _bloco_etapa_atual(progresso.__dict__)
        except Exception as e:
            logger.error(f"Erro ao renderizar etapa atual: {e}", exc_info=True)
            alert("❌ Erro ao carregar etapa atual.", "error")
    
    def _render_proximo_passo(self, progresso: JourneyProgress) -> None:
        """Renderiza próximo passo com tratamento de erros."""
        try:
            from views.patient.journey_blocks import _bloco_proximo_passo
            _bloco_proximo_passo(self.svc, progresso.__dict__, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar próximo passo: {e}", exc_info=True)
            alert("❌ Erro ao carregar próximo passo.", "error")
    
    def _render_tabs(self, progresso: JourneyProgress, jornada_id: str) -> None:
        """Renderiza as 4 tabs de jornada."""
        tab_etapas, tab_marcos, tab_eventos, tab_historia = st.tabs([
            "📋 Todas as Etapas",
            "🏁 Marcos Alcançados",
            "📅 Linha do Tempo",
            "💛 Minha História",
        ])
        
        with tab_etapas:
            self._render_tab_etapas(progresso)
        
        with tab_marcos:
            self._render_tab_marcos(jornada_id)
        
        with tab_eventos:
            self._render_tab_eventos(jornada_id)
        
        with tab_historia:
            self._render_tab_historia()
    
    def _render_tab_etapas(self, progresso: JourneyProgress) -> None:
        """Renderiza tab de todas as etapas com tratamento de erros."""
        try:
            _tab_todas_etapas(progresso.__dict__)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab etapas: {e}", exc_info=True)
            alert("❌ Erro ao carregar etapas.", "error")
    
    def _render_tab_marcos(self, jornada_id: str) -> None:
        """Renderiza tab de marcos com tratamento de erros."""
        try:
            render_marcos(self.db, jornada_id)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab marcos: {e}", exc_info=True)
            alert("❌ Erro ao carregar marcos.", "error")
    
    def _render_tab_eventos(self, jornada_id: str) -> None:
        """Renderiza tab de linha do tempo com tratamento de erros."""
        try:
            render_linha_do_tempo(self.db, jornada_id)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab eventos: {e}", exc_info=True)
            alert("❌ Erro ao carregar linha do tempo.", "error")
    
    def _render_tab_historia(self) -> None:
        """Renderiza tab de história com tratamento de erros."""
        try:
            from views.patient.journey_story import render as render_story
            render_story(self.services, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab história: {e}", exc_info=True)
            alert("❌ Erro ao carregar história.", "error")


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = JourneyRenderer(services, user)
    renderer.render()
