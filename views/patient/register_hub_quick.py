"""
Melshape — Card de Conquista para Compartilhamento.

Gera um card visual (HTML → st.components) que o paciente
pode capturar e compartilhar no Instagram, WhatsApp, etc.

Aquisição orgânica zero custo.
Gatilho: nova badge, streak especial (7, 14, 30, 90 dias), meta concluída.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

from views.components.cards import section_header, empty_state

logger = logging.getLogger("Melshape.ShareCard")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Dimensões do card
CARD_WIDTH = 360
CARD_HEIGHT = 400
CARD_BORDER_RADIUS = 24
CARD_PADDING = "2rem"

# Cores dos gradientes
CORES_STREAK = ("#C9A84C", "#3D5A73")
CORES_BADGE = ("#6366F1", "#3D5A73")
CORES_META = ("#10B981", "#065F46")

# Limiares
MIN_STREAK_PARA_CARD = 3

# Fallbacks
DEFAULT_NOME = "você"
DEFAULT_LEVEL = "Iniciante"
DEFAULT_PILAR_ICON = "🔥"
DEFAULT_PILAR_LABEL = "Transformação"

# Pilares
PILARES = {
    "general": ("⚖️", "Emagrecimento"),
    "fitness": ("💪", "Fitness"),
    "bariatric": ("🔪", "Pós-Bariátrica"),
    "glp1": ("💉", "GLP-1"),
}


@dataclass
class ShareCardData:
    """Dados para o card de compartilhamento."""
    nome: str = DEFAULT_NOME
    streak: int = 0
    health_mode: str = "general"
    level_name: str = DEFAULT_LEVEL
    xp: int = 0
    conquista_titulo: str = ""
    conquista_data: str = ""
    meta_titulo: str = ""


class ShareCardRenderer:
    """Renderer dedicado para cards de compartilhamento."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user or {}
        self.db = services.get("db")
        self.gami = services.get("gamification")
        self.nome = self._extrair_primeiro_nome()
        self.health_mode = user.get("health_mode", "general")
    
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
        """Renderiza tela de compartilhamento."""
        section_header(
            "📤 Compartilhar Conquista",
            "Mostre seu progresso para o mundo",
        )
        
        # Busca dados com cache
        streak = self._get_streak()
        conquistas = self._get_conquistas()
        stats = self._get_stats()
        
        # Tabs
        tab_streak, tab_badge, tab_meta = st.tabs([
            "🔥 Sequência",
            "🏅 Badge",
            "🎯 Meta",
        ])
        
        with tab_streak:
            self._render_tab_streak(streak, stats)
        
        with tab_badge:
            self._render_tab_badge(conquistas, stats)
        
        with tab_meta:
            self._render_tab_meta(stats)
    
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
    
    @st.cache_data(ttl=60)
    def _get_conquistas(_self) -> List[Dict]:
        """Obtém conquistas do usuário (com cache)."""
        if not _self.db:
            return []
        
        try:
            conquistas = _self.db.get_achievements()
            return conquistas if isinstance(conquistas, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter conquistas: {e}", exc_info=True)
            return []
    
    @st.cache_data(ttl=60)
    def _get_stats(_self) -> Dict[str, Any]:
        """Obtém estatísticas rápidas (com cache)."""
        if not _self.gami:
            return {}
        
        try:
            stats = _self.gami.quick_stats()
            return stats if isinstance(stats, dict) else {}
        except Exception as e:
            logger.error(f"Erro ao obter stats: {e}", exc_info=True)
            return {}
    
    def _render_tab_streak(self, streak: int, stats: Dict) -> None:
        """Renderiza tab de streak com tratamento de erros."""
        try:
            self._render_card_streak(streak, stats)
        except Exception as e:
            logger.error(f"Erro ao renderizar card streak: {e}", exc_info=True)
            empty_state("🔥", "Erro ao gerar card de sequência")
    
    def _render_card_streak(self, streak: int, stats: Dict) -> None:
        """Renderiza card de streak."""
        if streak < MIN_STREAK_PARA_CARD:
            self._render_mensagem_streak_minimo()
            return
        
        data = self._montar_data_streak(streak, stats)
        html = self._build_streak_card(data)
        
        st.components.v1.html(html, height=CARD_HEIGHT + 20)
        self._render_instrucoes()
    
    def _render_mensagem_streak_minimo(self) -> None:
        """Renderiza mensagem quando streak é insuficiente."""
        st.markdown(
            f"""
            <div style="font-size: 0.86rem; color: var(--text-muted); margin: 0.5rem 0;">
                Complete pelo menos <b>{MIN_STREAK_PARA_CARD} dias</b> seguidos para gerar seu card.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _montar_data_streak(self, streak: int, stats: Dict) -> ShareCardData:
        """Monta dados para card de streak."""
        return ShareCardData(
            nome=self.nome,
            streak=streak,
            health_mode=self.health_mode,
            level_name=stats.get("level_name", DEFAULT_LEVEL),
            xp=self._parse_int(stats.get("xp", 0)),
        )
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _render_tab_badge(self, conquistas: List[Dict], stats: Dict) -> None:
        """Renderiza tab de badge com tratamento de erros."""
        try:
            self._render_card_badge(conquistas, stats)
        except Exception as e:
            logger.error(f"Erro ao renderizar card badge: {e}", exc_info=True)
            empty_state("🏅", "Erro ao gerar card de conquista")
    
    def _render_card_badge(self, conquistas: List[Dict], stats: Dict) -> None:
        """Renderiza card de badge."""
        if not conquistas:
            empty_state(
                "🏅",
                "Nenhuma conquista ainda",
                "Complete hábitos e check-ins para desbloquear badges",
            )
            return
        
        ultima_conquista = conquistas[-1]
        data = self._montar_data_badge(ultima_conquista, stats)
        html = self._build_badge_card(data)
        
        st.components.v1.html(html, height=CARD_HEIGHT + 20)
        self._render_instrucoes()
    
    def _montar_data_badge(self, conquista: Dict, stats: Dict) -> ShareCardData:
        """Monta dados para card de badge."""
        titulo = conquista.get("title", conquista.get("achievement_name", "Conquista"))
        data_str = self._formatar_data(conquista.get("unlocked_at", ""))
        
        return ShareCardData(
            nome=self.nome,
            level_name=stats.get("level_name", DEFAULT_LEVEL),
            conquista_titulo=titulo,
            conquista_data=data_str,
        )
    
    def _formatar_data(self, data_raw: str) -> str:
        """Formata data de forma segura."""
        try:
            return data_raw[:10] if data_raw else "—"
        except Exception as e:
            logger.debug(f"Erro ao formatar data: {e}")
            return "—"
    
    def _render_tab_meta(self, stats: Dict) -> None:
        """Renderiza tab de meta com tratamento de erros."""
        try:
            self._render_card_meta(stats)
        except Exception as e:
            logger.error(f"Erro ao renderizar card meta: {e}", exc_info=True)
            empty_state("🎯", "Erro ao gerar card de meta")
    
    def _render_card_meta(self, stats: Dict) -> None:
        """Renderiza card de meta."""
        meta = self._get_ultima_meta_concluida()
        
        if not meta:
            empty_state(
                "🎯",
                "Nenhuma meta concluída ainda",
                "Conclua sua primeira meta para gerar o card",
            )
            return
        
        data = self._montar_data_meta(meta, stats)
        html = self._build_meta_card(data)
        
        st.components.v1.html(html, height=CARD_HEIGHT + 20)
        self._render_instrucoes()
    
    def _get_ultima_meta_concluida(self) -> Optional[Dict]:
        """Obtém última meta concluída com tratamento de erros."""
        try:
            jornada = self.db.get_jornada_ativa()
            
            if not jornada:
                return None
            
            metas = self.db.get_metas(jornada["id"])
            concluidas = [m for m in metas if m.get("concluida")]
            
            return concluidas[-1] if concluidas else None
        except Exception as e:
            logger.error(f"Erro ao obter última meta concluída: {e}", exc_info=True)
            return None
    
    def _montar_data_meta(self, meta: Dict, stats: Dict) -> ShareCardData:
        """Monta dados para card de meta."""
        return ShareCardData(
            nome=self.nome,
            level_name=stats.get("level_name", DEFAULT_LEVEL),
            xp=self._parse_int(stats.get("xp", 0)),
            meta_titulo=meta.get("titulo", "Meta concluída"),
        )
    
    def _build_streak_card(self, data: ShareCardData) -> str:
        """Constrói HTML do card de streak."""
        icon_p, label_p = self._get_pilar_info(data.health_mode)
        
        conteudo = f"""
            <div style="font-size: 3.5rem; margin-bottom: 0.5rem;">🔥</div>
            <div style="font-size: 1rem; color: rgba(255,255,255,.8);
                margin-bottom: 0.3rem;">{data.nome}</div>
            <div style="font-size: 4rem; font-weight: 900;
                font-family: Sora, sans-serif; line-height: 1;">
                {data.streak}
            </div>
            <div style="font-size: 1.1rem; color: rgba(255,255,255,.9);">
                dias consecutivos
            </div>
            <div style="margin-top: 1rem; font-size: 0.85rem;
                color: rgba(255,255,255,.7);">
                {icon_p} {label_p} · Nível {data.level_name} · {data.xp} XP
            </div>
            <div style="margin-top: 1.5rem; font-size: 0.75rem;
                color: rgba(255,255,255,.5);">
                melshape.com.br
            </div>
        """
        
        return self._base_card(conteudo, *CORES_STREAK)
    
    def _get_pilar_info(self, health_mode: str) -> tuple:
        """Obtém informações do pilar com fallback."""
        try:
            return PILARES.get(health_mode, (DEFAULT_PILAR_ICON, DEFAULT_PILAR_LABEL))
        except Exception as e:
            logger.debug(f"Erro ao obter info do pilar: {e}")
            return (DEFAULT_PILAR_ICON, DEFAULT_PILAR_LABEL)
    
    def _build_badge_card(self, data: ShareCardData) -> str:
        """Constrói HTML do card de badge."""
        conteudo = f"""
            <div style="font-size: 3.5rem; margin-bottom: 0.5rem;">🏅</div>
            <div style="font-size: 1rem; color: rgba(255,255,255,.8);
                margin-bottom: 0.5rem;">{data.nome} conquistou</div>
            <div style="font-size: 1.4rem; font-weight: 800;
                font-family: Sora, sans-serif; line-height: 1.2;
                padding: 0 1rem;">
                {data.conquista_titulo}
            </div>
            <div style="margin-top: 0.8rem; font-size: 0.85rem;
                color: rgba(255,255,255,.7);">
                Nível {data.level_name}
            </div>
            <div style="margin-top: 0.4rem; font-size: 0.78rem;
                color: rgba(255,255,255,.55);">
                {data.conquista_data}
            </div>
            <div style="margin-top: 1.5rem; font-size: 0.75rem;
                color: rgba(255,255,255,.5);">
                melshape.com.br
            </div>
        """
        
        return self._base_card(conteudo, *CORES_BADGE)
    
    def _build_meta_card(self, data: ShareCardData) -> str:
        """Constrói HTML do card de meta."""
        conteudo = f"""
            <div style="font-size: 3.5rem; margin-bottom: 0.5rem;">🎯</div>
            <div style="font-size: 1rem; color: rgba(255,255,255,.8);
                margin-bottom: 0.5rem;">{data.nome} concluiu a meta</div>
            <div style="font-size: 1.3rem; font-weight: 800;
                font-family: Sora, sans-serif; line-height: 1.3;
                padding: 0 1rem;">
                {data.meta_titulo}
            </div>
            <div style="margin-top: 1rem; font-size: 0.85rem;
                color: rgba(255,255,255,.7);">
                {data.xp} XP acumulados · Nível {data.level_name}
            </div>
            <div style="margin-top: 1.5rem; font-size: 0.75rem;
                color: rgba(255,255,255,.5);">
                melshape.com.br
            </div>
        """
        
        return self._base_card(conteudo, *CORES_META)
    
    def _base_card(self, conteudo: str, cor_inicio: str, cor_fim: str) -> str:
        """Constrói HTML base do card."""
        return f"""
        <div style="
            width: {CARD_WIDTH}px;
            height: {CARD_HEIGHT}px;
            background: linear-gradient(135deg, {cor_inicio}, {cor_fim});
            border-radius: {CARD_BORDER_RADIUS}px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            color: white;
            font-family: 'DM Sans', Arial, sans-serif;
            padding: {CARD_PADDING};
            box-shadow: 0 20px 60px rgba(0,0,0,.3);
            margin: 0 auto;
        ">
            {conteudo}
        </div>
        """
    
    def _render_instrucoes(self) -> None:
        """Renderiza instruções para compartilhamento."""
        st.markdown(
            """
            <div style="font-size: 0.80rem; color: var(--text-muted);
                text-align: center; margin-top: 0.9rem;">
                📸 Tire um print da tela e compartilhe no Instagram, 
                WhatsApp ou Stories!
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div style="font-size: 0.76rem; color: var(--text-faint);
                text-align: center; margin-top: 0.35rem;">
                #Melshape #Transformação #Consistência
            </div>
            """,
            unsafe_allow_html=True,
        )


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = ShareCardRenderer(services, user)
    renderer.render()
