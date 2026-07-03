"""
Melshape — Jornada: linha do tempo, marcos e listagem de etapas.
Importado por journey.py.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Tuple
import logging

from views.components.cards import empty_state

logger = logging.getLogger("Melshape.JourneyTimeline")


# Constantes de configuração de tipos
TIPO_CONFIG = {
    "checkin": ("✅", "var(--success)"),
    "pesagem": ("⚖️", "var(--primary)"),
    "refeicao": ("🍽️", "var(--warning)"),
    "marco": ("🏁", "var(--primary)"),
    "conquista": ("🏅", "var(--primary)"),
    "agua": ("💧", "var(--info)"),
    "habito": ("📋", "var(--text-muted)"),
}

# Constantes de limites
MAX_EVENTOS_LINHA_TEMPO = 20

# Fallbacks
DEFAULT_EMOJI = "📌"
DEFAULT_COR = "var(--text-muted)"
DEFAULT_ICONE_ETAPA = "📍"


class JourneyTimelineRenderer:
    """Renderer para linha do tempo da jornada."""
    
    def __init__(self, db):
        self.db = db
    
    def render_linha_do_tempo(self, jornada_id: str) -> None:
        """Renderiza linha do tempo com tratamento de erros."""
        eventos = self._get_eventos(jornada_id)
        
        if not eventos:
            empty_state(
                "📅",
                "Nenhum evento registrado ainda",
                "Suas ações vão aparecer aqui conforme você avança",
            )
            return
        
        self._render_header_eventos(len(eventos))
        
        for evento in eventos:
            self._render_evento_item(evento)
    
    @st.cache_data(ttl=30)
    def _get_eventos(_self, jornada_id: str) -> List[Dict]:
        """Obtém eventos da linha do tempo (com cache)."""
        if not jornada_id or not _self.db:
            return []
        
        try:
            eventos = _self.db.get_eventos(jornada_id, limit=MAX_EVENTOS_LINHA_TEMPO)
            return eventos if isinstance(eventos, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar eventos da jornada {jornada_id}: {e}", exc_info=True)
            return []
    
    def _render_header_eventos(self, total: int) -> None:
        """Renderiza cabeçalho de eventos."""
        st.markdown(
            f"""
            <div style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 0.9rem;">
                <b>{total}</b> evento(s) na sua jornada
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_evento_item(self, evento: Dict[str, Any]) -> None:
        """Renderiza um item de evento com tratamento de erros."""
        try:
            tipo = evento.get("tipo", "outro")
            emoji, cor = self._get_tipo_config(tipo)
            
            data_str = self._formatar_data_hora(evento.get("criado_em", ""))
            descricao = evento.get("descricao", "")
            
            self._render_card_evento(emoji, cor, data_str, descricao)
        except Exception as e:
            logger.error(f"Erro ao renderizar evento: {e}", exc_info=True)
    
    def _get_tipo_config(self, tipo: str) -> Tuple[str, str]:
        """Obtém configuração de tipo com fallback."""
        try:
            return TIPO_CONFIG.get(tipo, (DEFAULT_EMOJI, DEFAULT_COR))
        except Exception as e:
            logger.debug(f"Erro ao obter config do tipo '{tipo}': {e}")
            return (DEFAULT_EMOJI, DEFAULT_COR)
    
    def _formatar_data_hora(self, data_raw: str) -> str:
        """Formata data e hora de forma segura."""
        try:
            if not data_raw:
                return "—"
            
            # Remove segundos e milissegundos, mantém até minutos
            data_str = data_raw[:16].replace("T", " ")
            return data_str
        except Exception as e:
            logger.debug(f"Erro ao formatar data '{data_raw}': {e}")
            return "—"
    
    def _render_card_evento(self, emoji: str, cor: str, data_str: str, descricao: str) -> None:
        """Renderiza card de evento."""
        st.markdown(
            f"""
            <div style="display: flex; gap: 0.9rem; align-items: flex-start;
                padding: 0.7rem 0; border-bottom: 1px solid var(--border-subtle);">
                <div style="width: 30px; height: 30px; border-radius: 50%;
                    background: {cor}20; border: 2px solid {cor};
                    display: flex; align-items: center; justify-content: center;
                    font-size: 0.9rem; flex-shrink: 0;">{emoji}</div>
                <div style="flex: 1;">
                    <div style="font-size: 0.88rem; color: var(--text); font-weight: 500;">
                        {descricao}
                    </div>
                    <div style="font-size: 0.74rem; color: var(--text-faint); margin-top: 0.15rem;">
                        {data_str}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def render_marcos(self, jornada_id: str) -> None:
        """Renderiza marcos alcançados com tratamento de erros."""
        marcos = self._get_marcos(jornada_id)
        
        if not marcos:
            empty_state(
                "🏁",
                "Nenhum marco alcançado ainda",
                "Continue consistente — os marcos chegam automaticamente",
            )
            return
        
        self._render_header_marcos(len(marcos))
        
        for marco in marcos:
            self._render_marco_item(marco)
    
    @st.cache_data(ttl=60)
    def _get_marcos(_self, jornada_id: str) -> List[Dict]:
        """Obtém marcos da jornada (com cache)."""
        if not jornada_id or not _self.db:
            return []
        
        try:
            marcos = _self.db.get_marcos(jornada_id)
            return marcos if isinstance(marcos, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar marcos da jornada {jornada_id}: {e}", exc_info=True)
            return []
    
    def _render_header_marcos(self, total: int) -> None:
        """Renderiza cabeçalho de marcos."""
        st.markdown(
            f"""
            <div style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 0.9rem;">
                <b>{total}</b> marco(s) alcançado(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_marco_item(self, marco: Dict[str, Any]) -> None:
        """Renderiza um item de marco com tratamento de erros."""
        try:
            data_str = self._formatar_data(marco.get("data_marco", ""))
            titulo = marco.get("titulo", "Marco")
            descricao = marco.get("descricao", "")
            
            self._render_card_marco(data_str, titulo, descricao)
        except Exception as e:
            logger.error(f"Erro ao renderizar marco: {e}", exc_info=True)
    
    def _formatar_data(self, data_raw: str) -> str:
        """Formata data de forma segura."""
        try:
            if not data_raw:
                return "—"
            
            # Mantém apenas a data (YYYY-MM-DD)
            return data_raw[:10]
        except Exception as e:
            logger.debug(f"Erro ao formatar data '{data_raw}': {e}")
            return "—"
    
    def _render_card_marco(self, data_str: str, titulo: str, descricao: str) -> None:
        """Renderiza card de marco."""
        desc_html = (
            f'<div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.15rem;">'
            f'{descricao}</div>'
            if descricao else ""
        )
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom: 0.6rem;">
                <div style="display: flex; align-items: flex-start; gap: 0.8rem;">
                    <span style="font-size: 1.6rem;">🏁</span>
                    <div style="flex: 1;">
                        <div style="font-weight: 700; font-size: 0.94rem; color: var(--text);">
                            {titulo}
                        </div>
                        {desc_html}
                    </div>
                    <div style="font-size: 0.76rem; color: var(--text-faint); flex-shrink: 0;">
                        {data_str}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def render_todas_etapas(self, progresso: Dict[str, Any]) -> None:
        """Renderiza todas as etapas com tratamento de erros."""
        try:
            todas = self._obter_todas_etapas(progresso)
            
            if not todas:
                empty_state("📋", "Nenhuma etapa disponível")
                return
            
            for etapa in todas:
                self._render_etapa_item(etapa)
        except Exception as e:
            logger.error(f"Erro ao renderizar etapas: {e}", exc_info=True)
            empty_state("📋", "Erro ao carregar etapas")
    
    def _obter_todas_etapas(self, progresso: Dict[str, Any]) -> List[Dict]:
        """Obtém e ordena todas as etapas de forma segura."""
        try:
            concluidas = progresso.get("concluidas", [])
            pendentes = progresso.get("pendentes", [])
            
            if not isinstance(concluidas, list):
                concluidas = []
            if not isinstance(pendentes, list):
                pendentes = []
            
            todas = concluidas + pendentes
            
            # Ordena por ordem
            todas_sorted = sorted(
                todas,
                key=lambda x: self._parse_int(x.get("ordem", 0)),
            )
            
            return todas_sorted
        except Exception as e:
            logger.error(f"Erro ao obter todas as etapas: {e}", exc_info=True)
            return []
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _render_etapa_item(self, etapa: Dict[str, Any]) -> None:
        """Renderiza um item de etapa com tratamento de erros."""
        try:
            concluida = etapa.get("concluida", False)
            icone = etapa.get("icone", DEFAULT_ICONE_ETAPA)
            ordem = self._parse_int(etapa.get("ordem", 0))
            nome = etapa.get("nome", "")
            descricao = etapa.get("descricao", "")
            
            cor_borda = self._get_cor_borda_etapa(concluida)
            cor_texto = self._get_cor_texto_etapa(concluida)
            badge_html = self._get_badge_concluida(concluida)
            
            self._render_card_etapa(
                icone, ordem, nome, descricao,
                cor_borda, cor_texto, badge_html
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar etapa: {e}", exc_info=True)
    
    def _get_cor_borda_etapa(self, concluida: bool) -> str:
        """Retorna cor da borda baseada no status da etapa."""
        return "var(--success)" if concluida else "var(--border)"
    
    def _get_cor_texto_etapa(self, concluida: bool) -> str:
        """Retorna cor do texto baseada no status da etapa."""
        return "var(--text-muted)" if concluida else "var(--text)"
    
    def _get_badge_concluida(self, concluida: bool) -> str:
        """Retorna HTML do badge de concluída."""
        if not concluida:
            return ""
        
        return """
            <span style="padding: 0.15rem 0.6rem; border-radius: 9999px;
                font-size: 0.74rem; font-weight: 700; flex-shrink: 0;
                background: var(--success-bg); color: var(--success);
                border: 1px solid var(--success);">✅ Concluída</span>
        """
    
    def _render_card_etapa(
        self,
        icone: str,
        ordem: int,
        nome: str,
        descricao: str,
        cor_borda: str,
        cor_texto: str,
        badge_html: str,
    ) -> None:
        """Renderiza card de etapa."""
        st.markdown(
            f"""
            <div style="display: flex; align-items: flex-start; gap: 0.9rem;
                padding: 0.9rem; border: 1px solid {cor_borda};
                border-radius: 12px; margin-bottom: 0.6rem;
                background: var(--surface);">
                <span style="font-size: 1.6rem; flex-shrink: 0;">{icone}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 700; font-size: 0.94rem; color: {cor_texto};">
                        Etapa {ordem} — {nome}
                    </div>
                    <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.15rem;">
                        {descricao}
                    </div>
                </div>
                {badge_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


# Funções de compatibilidade
def render_linha_do_tempo(db, jornada_id: str) -> None:
    """Renderiza linha do tempo (compatibilidade)."""
    renderer = JourneyTimelineRenderer(db)
    renderer.render_linha_do_tempo(jornada_id)


def render_marcos(db, jornada_id: str) -> None:
    """Renderiza marcos (compatibilidade)."""
    renderer = JourneyTimelineRenderer(db)
    renderer.render_marcos(jornada_id)


def _tab_todas_etapas(progresso: Dict[str, Any]) -> None:
    """Renderiza todas as etapas (compatibilidade)."""
    renderer = JourneyTimelineRenderer(None)
    renderer.render_todas_etapas(progresso)
