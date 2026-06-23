"""
Melshape — Evolução Completa.

Reúne 8 funcionalidades ausentes em uma tela com 4 abas:
  📏 Corpo    → medidas corporais + fotos
  🧪 Clínico  → exames + estagnação
  🏆 Conquistas → hall da fama + carteira + histórico XP
  ⚖️ Legal    → consentimentos LGPD + revogação

Correções vs versão original:
  - self.uid → self._uid() (método, não property)
  - Guard clauses em todos os gráficos Plotly
  - Contextualizer aplicado (números→narrativa)
  - Revogação de consentimento implementada
  - Campos de medida alinhados com banco real
"""
import streamlit as st
from typing import Dict, Any, Optional
import logging

from services.evolution_service import EvolutionService
from views.components.cards import section_header, alert
from views.patient.evolution_corpo import _tab_corpo
from views.patient.evolution_clinico import _tab_clinico
from views.patient.evolution_gami import _tab_conquistas
from views.patient.evolution_legal import _tab_legal

logger = logging.getLogger("Melshape.Evolution")


class EvolutionRenderer:
    """Renderer dedicado para evolução completa."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.svc = self._init_evolution_service()
    
    def _init_evolution_service(self) -> Optional[EvolutionService]:
        """Inicializa EvolutionService com tratamento de erros."""
        if not self.db:
            logger.error("Database não disponível para EvolutionRenderer")
            return None
        
        try:
            return EvolutionService(self.db)
        except Exception as e:
            logger.error(f"Erro ao inicializar EvolutionService: {e}", exc_info=True)
            return None
    
    def render(self) -> None:
        """Renderiza tela de evolução completa."""
        section_header(
            "📊 Evolução Completa",
            "Corpo, exames, conquistas e privacidade em um só lugar",
        )
        
        # Verifica se serviço foi inicializado
        if not self.svc:
            self._render_error_state()
            return
        
        # Renderiza tabs
        self._render_tabs()
    
    def _render_error_state(self) -> None:
        """Renderiza estado de erro quando serviço não está disponível."""
        alert(
            "❌ Não foi possível carregar o módulo de evolução. "
            "Por favor, recarregue a página ou entre em contato com o suporte.",
            "error",
        )
    
    def _render_tabs(self) -> None:
        """Renderiza as 4 tabs de evolução."""
        tab_corpo, tab_clinico, tab_conquistas, tab_legal = st.tabs([
            "📏 Corpo",
            "🧪 Clínico",
            "🏆 Conquistas",
            "⚖️ Legal",
        ])
        
        with tab_corpo:
            self._render_tab_corpo()
        
        with tab_clinico:
            self._render_tab_clinico()
        
        with tab_conquistas:
            self._render_tab_conquistas()
        
        with tab_legal:
            self._render_tab_legal()
    
    def _render_tab_corpo(self) -> None:
        """Renderiza tab de corpo com tratamento de erros."""
        try:
            _tab_corpo(self.svc, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab Corpo: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados corporais.", "error")
    
    def _render_tab_clinico(self) -> None:
        """Renderiza tab clínico com tratamento de erros."""
        try:
            _tab_clinico(self.svc, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab Clínico: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados clínicos.", "error")
    
    def _render_tab_conquistas(self) -> None:
        """Renderiza tab de conquistas com tratamento de erros."""
        try:
            _tab_conquistas(self.svc, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab Conquistas: {e}", exc_info=True)
            alert("❌ Erro ao carregar conquistas.", "error")
    
    def _render_tab_legal(self) -> None:
        """Renderiza tab legal com tratamento de erros."""
        try:
            _tab_legal(self.svc, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab Legal: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados legais.", "error")


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = EvolutionRenderer(services, user)
    renderer.render()
