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
        """
        Renderiza página inicial.

        Estrutura de 3 blocos (Constituição Cap. VI — Uma Única Ação Principal):
          1. Saudação + próximo passo  → O que faço agora?
          2. Consistência + hábitos    → Como estou indo?
          3. Contexto do pilar         → O que é relevante para minha jornada?

        Tudo mais (score, gamificação, consequências) está acessível via
        navegação — não ocupa espaço da home. Dia 1 com dados zerados mostra
        direcionamento claro, não painel vazio.
        """
        # Notificações silenciosas (toasts apenas)
        self._render_notificacoes_conquistas()

        # ── BLOCO 1: Saudação + Próximo Passo ────────────────────────────────
        self._render_saudacao()
        self._render_next_step()

        st.divider()

        # ── BLOCO 2: Consistência + Hábitos de Hoje ──────────────────────────
        self._render_bloco_consistencia_compacto()

        st.divider()

        # ── BLOCO 3: Contexto do Pilar ────────────────────────────────────────
        self._render_contexto_pilar()

        # CTA de check-in (só aparece se não fez hoje)
        self._render_checkin_cta()

    def _render_dia_1(self) -> None:
        """
        Estado dia 1: sem dados, sem painel vazio.

        Missão: dar UMA direção clara — o check-in — com acolhimento.
        Constituição: 'Uma Única Ação Principal' + 'Humanização'.
        """
        nome = self.nome or "você"
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="text-align:center;
                padding:2rem 1.5rem;border-color:var(--primary-border);
                background:var(--primary-light);">
                <div style="font-size:2.5rem;margin-bottom:0.6rem;">🌱</div>
                <div style="font-family:var(--font-display);font-weight:800;
                    font-size:1.15rem;color:var(--text);margin-bottom:0.4rem;">
                    Sua jornada começa hoje, {nome}.
                </div>
                <div style="font-size:0.88rem;color:var(--text-muted);
                    line-height:1.6;max-width:320px;margin:0 auto;">
                    O primeiro passo é o check-in diário.<br>
                    Leva 30 segundos e define o ritmo de tudo.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "✅ Fazer meu primeiro check-in",
            type="primary",
            use_container_width=True,
            key="home_dia1_cta",
        ):
            st.session_state.page = "checkin"
            st.rerun()


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
    
    def _render_contexto_pilar(self) -> None:
        """Renderiza contexto do pilar com tratamento de erros."""
        try:
            render_contexto_pilar(self.services, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar contexto do pilar: {e}", exc_info=True)
            alert("❌ Erro ao carregar contexto do pilar.", "error")
    
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
