"""
Melshape — Home do Paciente (Reorganizada — Nível 5).

HIERARQUIA ABSOLUTA:
  1. Consistência (streak + check-in)
  2. Hábitos de Hoje
  3. Comportamento (check-in emocional)
  4. Consequências (calorias, proteína, água, peso)

Peso e calorias são consequências — nunca a primeira coisa que o paciente vê.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Tuple
from datetime import date, datetime
import logging
import random

from views.components.next_step import render_next_step
from views.patient.home_consistency import _bloco_consistencia
from views.patient.home_blocks import _bloco_xp, _bloco_desafio
from views.patient.home_helpers import _get_last_weight, _get_dashboard_paciente
from views.patient.home_context import render_contexto_pilar
from views.components.notification_inbox import exibir_notificacoes
from views.components.cards import (
    motivational_quote, alert, empty_state,
    show_new_achievements,
)
from services.contextualizer import ctx
import config

logger = logging.getLogger("Melshape.Home")


# Constantes de modos de saúde
MODE_LABELS = {
    "general": ("⚖️", "Emagrecimento"),
    "fitness": ("💪", "Fitness"),
    "bariatric": ("🔪", "Pós-Bariátrica"),
    "glp1": ("💉", "GLP-1"),
}

# Frases motivacionais por pilar
QUOTES = {
    "general": [
        "Consistência bate perfeição todos os dias.",
        "Um dia de cada vez. Isso é tudo que precisa.",
        "Você não precisa ser extremo. Só precisa ser constante.",
    ],
    "fitness": [
        "O corpo muda devagar. A disciplina muda rápido.",
        "Cada treino é uma promessa cumprida com você mesmo.",
    ],
    "bariatric": [
        "Cada refeição certa é uma vitória clínica real.",
        "Seu corpo está se reconstruindo. Respeite o processo.",
    ],
    "glp1": [
        "O medicamento abre a porta. Você decide o que entra.",
        "Proteína primeiro. Sempre.",
    ],
}

# Fallbacks
QUOTE_FALLBACK = "Cada passo conta. Continue."
DEFAULT_NOME = "você"


class HomeRenderer:
    """Renderer dedicado para página inicial do paciente."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.nutr = services.get("nutrition")
        self.gami = services.get("gamification")
        self.health_mode = user.get("health_mode", "general")
        self.nome = self._extrair_primeiro_nome()
    
    def _extrair_primeiro_nome(self) -> str:
        """Extrai primeiro nome do usuário de forma segura."""
        try:
            nome_completo = self.user.get("name", "")
            if not nome_completo:
                return DEFAULT_NOME
            partes = nome_completo.split()
            return partes[0] if partes else DEFAULT_NOME
        except Exception as e:
            logger.debug(f"Erro ao extrair primeiro nome: {e}")
            return DEFAULT_NOME
    
    def render(self) -> None:
        """Renderiza página inicial."""
        # Notificações e conquistas
        self._render_notificacoes_conquistas()
        
        # Saudação
        self._render_saudacao()
        
        # Próximo passo
        self._render_next_step()
        
        st.divider()
        
        # Bloco 1: Consistência
        self._render_bloco_consistencia()
        
        st.divider()
        
        # Bloco 2: Hábitos de hoje
        self._render_habitos_hoje()
        
        st.divider()
        
        # Bloco 3: Comportamento
        self._render_comportamento()
        
        st.divider()
        
        # Bloco 4: Contexto do pilar
        self._render_contexto_pilar()
        
        st.divider()
        
        # Bloco 5: Consequências
        self._render_consequencias()
        
        st.divider()
        
        # Bloco 6: Gamificação + Score
        self._render_gamificacao()
        
        st.divider()
        
        # Bloco 7: Score narrativo
        self._render_score()
        
        st.divider()
        
        # Frase motivacional
        self._render_motivacao()
        
        # CTA check-in
        self._render_checkin_cta()
    
    def _render_notificacoes_conquistas(self) -> None:
        """Renderiza notificações e conquistas novas."""
        try:
            exibir_notificacoes(self.services, self.user)
        except Exception as e:
            logger.error(f"Erro ao exibir notificações: {e}", exc_info=True)
        
        # Conquistas novas
        novos_ach = self._get_novas_conquistas()
        if novos_ach:
            try:
                show_new_achievements(novos_ach)
            except Exception as e:
                logger.error(f"Erro ao exibir novas conquistas: {e}", exc_info=True)
    
    @st.cache_data(ttl=30)
    def _get_novas_conquistas(_self) -> List[Dict]:
        """Obtém novas conquistas (com cache)."""
        if not _self.gami:
            return []
        
        try:
            novos = _self.gami.check_achievements(_self.user)
            return novos if isinstance(novos, list) else []
        except Exception as e:
            logger.error(f"Erro ao verificar conquistas: {e}", exc_info=True)
            return []
    
    def _render_next_step(self) -> None:
        """Renderiza próximo passo com tratamento de erros."""
        try:
            render_next_step(self.services, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar próximo passo: {e}", exc_info=True)
    
    def _render_saudacao(self) -> None:
        """Renderiza saudação personalizada."""
        turno = self._get_turno()
        icone, _ = self._get_mode_info()
        data_br = self._get_data_br()
        
        st.markdown(
            f"""
            <div class="fade-in" style="margin-bottom: 1rem;">
                <h1 style="font-family: var(--font-display); font-weight: 800;
                    font-size: 1.7rem; color: var(--text); margin: 0;">
                    {turno}, {self.nome} {icone}
                </h1>
                <p style="color: var(--text-muted); font-size: 0.88rem;
                    margin: 0.2rem 0 0;">{data_br}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_mode_info(self) -> Tuple[str, str]:
        """Obtém ícone e label do modo de saúde."""
        try:
            return MODE_LABELS.get(self.health_mode, ("⚖️", "Geral"))
        except Exception as e:
            logger.debug(f"Erro ao obter info do modo: {e}")
            return ("⚖️", "Geral")
    
    @st.cache_data(ttl=60)
    def _get_turno(_self) -> str:
        """Obtém saudação baseada no horário (com cache)."""
        try:
            from views.patient.home_daily import _turno
            return _turno()
        except Exception as e:
            logger.error(f"Erro ao obter turno: {e}")
            return "Olá"
    
    @st.cache_data(ttl=60)
    def _get_data_br(_self) -> str:
        """Obtém data no formato brasileiro (com cache)."""
        try:
            from views.patient.home_daily import _data_br
            return _data_br()
        except Exception as e:
            logger.error(f"Erro ao obter data BR: {e}")
            return ""
    
    def _render_bloco_consistencia(self) -> None:
        """Renderiza bloco de consistência com tratamento de erros."""
        try:
            streak = self._get_streak()
            checkin = self._get_checkin_hoje()
            _bloco_consistencia(streak, checkin, self.db, self.gami, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar bloco consistência: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados de consistência.", "error")
    
    @st.cache_data(ttl=30)
    def _get_streak(_self) -> int:
        """Obtém streak de check-ins (com cache)."""
        if not _self.db:
            return 0
        
        try:
            streak = _self.db.get_checkin_streak()
            return int(streak) if streak is not None else 0
        except Exception as e:
            logger.error(f"Erro ao obter streak: {e}", exc_info=True)
            return 0
    
    @st.cache_data(ttl=30)
    def _get_checkin_hoje(_self) -> Optional[Dict]:
        """Obtém check-in de hoje (com cache)."""
        if not _self.db:
            return None
        
        try:
            return _self.db.get_checkin_today()
        except Exception as e:
            logger.error(f"Erro ao obter check-in de hoje: {e}", exc_info=True)
            return None
    
    def _render_habitos_hoje(self) -> None:
        """Renderiza bloco de hábitos de hoje com tratamento de erros."""
        try:
            from views.patient.home_daily import _bloco_habitos_hoje
            _bloco_habitos_hoje(self.db, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar hábitos de hoje: {e}", exc_info=True)
            alert("❌ Erro ao carregar hábitos de hoje.", "error")
    
    def _render_comportamento(self) -> None:
        """Renderiza bloco de comportamento com tratamento de erros."""
        try:
            from views.patient.home_daily import _bloco_comportamento
            checkin = self._get_checkin_hoje()
            _bloco_comportamento(checkin)
        except Exception as e:
            logger.error(f"Erro ao renderizar comportamento: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados de comportamento.", "error")
    
    def _render_contexto_pilar(self) -> None:
        """Renderiza contexto do pilar com tratamento de erros."""
        try:
            render_contexto_pilar(self.services, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar contexto do pilar: {e}", exc_info=True)
            alert("❌ Erro ao carregar contexto do pilar.", "error")
    
    def _render_consequencias(self) -> None:
        """Renderiza bloco de consequências com tratamento de erros."""
        try:
            from views.patient.home_daily import _bloco_consequencias
            
            sm = self._get_daily_summary()
            hydration = self._get_hydration()
            last_weight = self._get_last_weight()
            
            _bloco_consequencias(
                sm, hydration, self.user,
                self.nutr, last_weight
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar consequências: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados nutricionais.", "error")
    
    @st.cache_data(ttl=60)
    def _get_daily_summary(_self) -> Optional[Dict]:
        """Obtém resumo diário de nutrição (com cache)."""
        if not _self.nutr:
            return None
        
        try:
            return _self.nutr.daily_summary()
        except Exception as e:
            logger.error(f"Erro ao obter daily summary: {e}", exc_info=True)
            return None
    
    @st.cache_data(ttl=30)
    def _get_hydration(_self) -> Optional[Dict]:
        """Obtém hidratação de hoje (com cache)."""
        if not _self.db:
            return None
        
        try:
            return _self.db.get_hydration_today()
        except Exception as e:
            logger.error(f"Erro ao obter hidratação: {e}", exc_info=True)
            return None
    
    @st.cache_data(ttl=60)
    def _get_last_weight(_self) -> Optional[float]:
        """Obtém último peso registrado (com cache)."""
        if not _self.db:
            return None
        
        try:
            return _get_last_weight(_self.db)
        except Exception as e:
            logger.error(f"Erro ao obter último peso: {e}", exc_info=True)
            return None
    
    def _render_gamificacao(self) -> None:
        """Renderiza bloco de gamificação com tratamento de erros."""
        try:
            col_gami, col_desafio = st.columns([1, 1])
            
            with col_gami:
                stats = self._get_quick_stats()
                dash_pac = self._get_dashboard_paciente()
                _bloco_xp(stats, dash_pac)
            
            with col_desafio:
                _bloco_desafio(self.gami)
        except Exception as e:
            logger.error(f"Erro ao renderizar gamificação: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados de gamificação.", "error")
    
    @st.cache_data(ttl=60)
    def _get_quick_stats(_self) -> Dict[str, Any]:
        """Obtém estatísticas rápidas (com cache)."""
        if not _self.gami:
            return {}
        
        try:
            stats = _self.gami.quick_stats()
            return stats if isinstance(stats, dict) else {}
        except Exception as e:
            logger.error(f"Erro ao obter quick stats: {e}", exc_info=True)
            return {}
    
    @st.cache_data(ttl=60)
    def _get_dashboard_paciente(_self) -> Optional[Dict]:
        """Obtém dashboard do paciente (com cache)."""
        if not _self.db:
            return None
        
        try:
            return _get_dashboard_paciente(_self.db)
        except Exception as e:
            logger.error(f"Erro ao obter dashboard: {e}", exc_info=True)
            return None
    
    def _render_score(self) -> None:
        """Renderiza score narrativo com tratamento de erros."""
        try:
            from views.patient.home_daily import _bloco_score
            _bloco_score(self.services, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar score: {e}", exc_info=True)
            alert("❌ Erro ao carregar score narrativo.", "error")
    
    def _render_motivacao(self) -> None:
        """Renderiza frase motivacional com fallback seguro."""
        try:
            quotes = QUOTES.get(self.health_mode, QUOTES["general"])
            
            if not quotes:
                motivational_quote(QUOTE_FALLBACK)
                return
            
            quote = random.choice(quotes)
            motivational_quote(quote)
        except Exception as e:
            logger.error(f"Erro ao renderizar motivação: {e}", exc_info=True)
            motivational_quote(QUOTE_FALLBACK)
    
    def _render_checkin_cta(self) -> None:
        """Renderiza CTA para check-in."""
        checkin = self._get_checkin_hoje()
        
        if checkin:
            return
        
        st.markdown('<div style="margin-top: 0.8rem;"></div>', unsafe_allow_html=True)
        
        alert(
            "Você ainda não fez o check-in de hoje. "
            "Leva menos de 30 segundos! ✅",
            "info",
        )
        
        if st.button(
            "Fazer check-in agora →",
            type="primary",
            use_container_width=True,
            key="home_checkin_cta",
        ):
            st.session_state.page = "checkin"
            st.rerun()


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = HomeRenderer(services, user)
    renderer.render()
