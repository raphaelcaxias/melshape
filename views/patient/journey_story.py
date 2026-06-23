"""
Melshape — Narrativa da Jornada (UNIFICADO).

Elimina journey_story_tabs.py — sem import circular.
O paciente vê: motivos, fotos, conquistas, eventos de vida.

Princípio: lembrar o "porquê" é o principal antídoto contra abandono.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
import logging

from views.components.cards import (
    section_header, empty_state, alert, motivational_quote,
)
from views.patient.journey_story_forms import (
    render_form_motivo, render_form_foto, render_form_evento,
)

logger = logging.getLogger("Melshape.JourneyStory")


# Constantes de ícones por tipo de evento
TIPO_ICON = {
    "marco": "🏁",
    "desafio": "⚡",
    "celebracao": "🎉",
    "dificuldade": "💪",
    "inicio": "🌱",
}

# Constantes de limites
MAX_FOTOS_EXIBIR = 6
DEFAULT_NOME = "você"


class JourneyStoryRenderer:
    """Renderer dedicado para narrativa da jornada."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
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
        """Renderiza narrativa da jornada."""
        section_header(
            "💛 Sua História",
            "Por que você começou. Quanto já evoluiu."
        )
        
        # Garante que jornada existe
        jornada = self._garantir_jornada()
        jornada_id = jornada.get("id", "") if jornada else ""
        
        # Tabs
        self._render_tabs(jornada_id)
    
    def _garantir_jornada(self) -> Optional[Dict]:
        """Garante que jornada existe com tratamento de erros."""
        try:
            from services.journey_service import JourneyService
            svc = JourneyService(self.db)
            return svc.garantir_jornada(self.user)
        except Exception as e:
            logger.error(f"Erro ao garantir jornada: {e}", exc_info=True)
            return None
    
    def _render_tabs(self, jornada_id: str) -> None:
        """Renderiza as 4 tabs da narrativa."""
        tab_motivo, tab_fotos, tab_conquistas, tab_vida = st.tabs([
            "💛 Por que Comecei",
            "📸 Evolução Visual",
            "🏅 Conquistas",
            "📅 Momentos",
        ])
        
        with tab_motivo:
            self._render_tab_motivo(jornada_id)
        
        with tab_fotos:
            self._render_tab_fotos()
        
        with tab_conquistas:
            self._render_tab_conquistas(jornada_id)
        
        with tab_vida:
            self._render_tab_eventos_vida()
    
    def _render_tab_motivo(self, jornada_id: str) -> None:
        """Renderiza tab de motivos com tratamento de erros."""
        try:
            self._render_motivo(jornada_id)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab motivos: {e}", exc_info=True)
            alert("❌ Erro ao carregar motivos.", "error")
    
    def _render_motivo(self, jornada_id: str) -> None:
        """Renderiza motivos do paciente."""
        motivos = self._get_motivos(jornada_id)
        
        if motivos:
            self._render_motivos_registrados(motivos)
            self._render_alerta_streak_zero()
        else:
            self._render_mensagem_sem_motivo()
        
        if jornada_id:
            render_form_motivo(self.db, jornada_id, has_motivo=bool(motivos))
    
    @st.cache_data(ttl=60)
    def _get_motivos(_self, jornada_id: str) -> List[Dict]:
        """Obtém motivos do paciente (com cache)."""
        if not jornada_id or not _self.db:
            return []
        
        try:
            motivos = _self.db.get_motivos(jornada_id)
            return motivos if isinstance(motivos, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar motivos: {e}", exc_info=True)
            return []
    
    def _render_motivos_registrados(self, motivos: List[Dict]) -> None:
        """Renderiza motivos registrados."""
        st.markdown(
            """
            <p style="font-size: 0.74rem; font-weight: 700; letter-spacing: 0.06em;
                color: var(--text-faint); text-transform: uppercase;
                margin-bottom: 0.9rem;">
                Seu porquê
            </p>
            """,
            unsafe_allow_html=True,
        )
        
        for motivo in motivos:
            texto = motivo.get("motivo", "")
            if texto:
                motivational_quote(texto)
    
    def _render_alerta_streak_zero(self) -> None:
        """Renderiza alerta quando streak é zero."""
        try:
            streak = self._get_streak()
            
            if streak == 0:
                alert(
                    f"💛 {self.nome}, lembre-se do seu porquê. "
                    f"Cada recomeço conta.",
                    "info",
                )
        except Exception as e:
            logger.error(f"Erro ao verificar streak: {e}", exc_info=True)
    
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
    
    def _render_mensagem_sem_motivo(self) -> None:
        """Renderiza mensagem quando não há motivos."""
        st.markdown(
            """
            <div style="font-size: 0.88rem; color: var(--text-muted); margin-bottom: 1.2rem;">
                Registre seu porquê. É o que vai te fazer voltar nos dias difíceis.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_tab_fotos(self) -> None:
        """Renderiza tab de fotos com tratamento de erros."""
        try:
            self._render_fotos()
        except Exception as e:
            logger.error(f"Erro ao renderizar tab fotos: {e}", exc_info=True)
            alert("❌ Erro ao carregar fotos.", "error")
    
    def _render_fotos(self) -> None:
        """Renderiza fotos de evolução."""
        perfil_id = self._get_perfil_id()
        
        if not perfil_id:
            alert("❌ Não foi possível identificar seu perfil.", "error")
            return
        
        fotos = self._get_fotos(perfil_id)
        
        if fotos:
            self._render_lista_fotos(fotos)
        else:
            empty_state(
                "📸",
                "Nenhuma foto ainda",
                "Registre sua evolução visual — é um motivador poderoso",
            )
        
        st.markdown("---")
        render_form_foto(self.db, perfil_id, self.user)
    
    def _get_perfil_id(self) -> Optional[str]:
        """Obtém ID do perfil com tratamento de erros."""
        try:
            return self.db.uid()
        except Exception as e:
            logger.error(f"Erro ao obter perfil ID: {e}", exc_info=True)
            return None
    
    @st.cache_data(ttl=60)
    def _get_fotos(_self, perfil_id: str) -> List[Dict]:
        """Obtém fotos do paciente (com cache)."""
        if not perfil_id or not _self.db:
            return []
        
        try:
            fotos = _self.db.get_fotos(perfil_id)
            return fotos if isinstance(fotos, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar fotos: {e}", exc_info=True)
            return []
    
    def _render_lista_fotos(self, fotos: List[Dict]) -> None:
        """Renderiza lista de fotos."""
        st.markdown(
            f"""
            <div style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 0.9rem;">
                <b>{len(fotos)}</b> foto(s) de evolução registrada(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        cols = st.columns(2)
        
        for i, foto in enumerate(fotos[:MAX_FOTOS_EXIBIR]):
            with cols[i % 2]:
                self._render_foto_item(foto)
    
    def _render_foto_item(self, foto: Dict[str, Any]) -> None:
        """Renderiza um item de foto com tratamento de erros."""
        url = foto.get("url_foto", "")
        legenda = foto.get("legenda", "")
        data = self._formatar_data(foto.get("data_foto", ""))
        peso = foto.get("peso_na_data")
        
        info = self._formatar_info_foto(data, peso)
        
        if url.startswith("http"):
            self._render_imagem_url(url, legenda, info)
        else:
            self._render_placeholder_foto(info, legenda)
    
    def _formatar_data(self, data_raw: str) -> str:
        """Formata data de forma segura."""
        try:
            return data_raw[:10] if data_raw else "—"
        except Exception as e:
            logger.debug(f"Erro ao formatar data: {e}")
            return "—"
    
    def _formatar_info_foto(self, data: str, peso: Optional[float]) -> str:
        """Formata informação da foto."""
        try:
            if peso:
                return f"{data} · {peso:.1f}kg"
            return data
        except Exception as e:
            logger.debug(f"Erro ao formatar info da foto: {e}")
            return data
    
    def _render_imagem_url(self, url: str, legenda: str, info: str) -> None:
        """Renderiza imagem a partir de URL."""
        try:
            caption = legenda or info
            st.image(url, caption=caption, use_container_width=True)
        except Exception as e:
            logger.error(f"Erro ao renderizar imagem '{url}': {e}", exc_info=True)
            self._render_placeholder_foto(info, legenda)
    
    def _render_placeholder_foto(self, info: str, legenda: str) -> None:
        """Renderiza placeholder quando foto não está disponível."""
        legenda_html = f"<br>{legenda}" if legenda else ""
        
        st.markdown(
            f"""
            <div style="background: var(--surface-2);
                border: 1px solid var(--border);
                border-radius: 12px; padding: 1.3rem; text-align: center;
                color: var(--text-muted); font-size: 0.82rem;">
                📸 {info}{legenda_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_tab_conquistas(self, jornada_id: str) -> None:
        """Renderiza tab de conquistas com tratamento de erros."""
        try:
            self._render_conquistas(jornada_id)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab conquistas: {e}", exc_info=True)
            alert("❌ Erro ao carregar conquistas.", "error")
    
    def _render_conquistas(self, jornada_id: str) -> None:
        """Renderiza conquistas da jornada."""
        if not jornada_id:
            empty_state("🏅", "Jornada não iniciada")
            return
        
        conquistas = self._get_conquistas_jornada(jornada_id)
        
        if conquistas:
            self._render_lista_conquistas(conquistas)
        else:
            empty_state(
                "🏅",
                "Nenhuma conquista específica ainda",
                "Continue consistente — as conquistas chegam com o progresso",
            )
    
    @st.cache_data(ttl=60)
    def _get_conquistas_jornada(_self, jornada_id: str) -> List[Dict]:
        """Obtém conquistas da jornada (com cache)."""
        if not jornada_id or not _self.db:
            return []
        
        try:
            conquistas = _self.db.get_conquistas_jornada(jornada_id)
            return conquistas if isinstance(conquistas, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar conquistas: {e}", exc_info=True)
            return []
    
    def _render_lista_conquistas(self, conquistas: List[Dict]) -> None:
        """Renderiza lista de conquistas."""
        st.markdown(
            f"""
            <div style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 0.9rem;">
                🏅 <b>{len(conquistas)}</b> conquista(s) nesta jornada
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        for conquista in conquistas:
            self._render_conquista_item(conquista)
    
    def _render_conquista_item(self, conquista: Dict[str, Any]) -> None:
        """Renderiza um item de conquista."""
        data = self._formatar_data(conquista.get("conquistado_em", ""))
        titulo = conquista.get("titulo", "Conquista")
        descricao = conquista.get("descricao", "")
        
        desc_html = (
            f'<div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.2rem;">'
            f'{descricao}</div>'
            if descricao else ""
        )
        
        st.markdown(
            f"""
            <div style="display: flex; align-items: flex-start; gap: 0.8rem;
                padding: 0.8rem; background: var(--primary-light);
                border: 1px solid var(--primary-border);
                border-radius: 12px; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">🏅</span>
                <div style="flex: 1;">
                    <div style="font-weight: 700; font-size: 0.94rem; color: var(--text);">
                        {titulo}
                    </div>
                    {desc_html}
                </div>
                <span style="font-size: 0.76rem; color: var(--text-faint);">
                    {data}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_tab_eventos_vida(self) -> None:
        """Renderiza tab de eventos de vida com tratamento de erros."""
        try:
            self._render_eventos_vida()
        except Exception as e:
            logger.error(f"Erro ao renderizar tab eventos: {e}", exc_info=True)
            alert("❌ Erro ao carregar eventos.", "error")
    
    def _render_eventos_vida(self) -> None:
        """Renderiza eventos de vida."""
        eventos = self._get_eventos_vida()
        
        if eventos:
            for evento in eventos:
                self._render_evento_item(evento)
        else:
            empty_state(
                "📅",
                "Nenhum momento registrado",
                "Guarde os momentos importantes da sua transformação",
            )
        
        st.markdown("---")
        render_form_evento(self.db)
    
    @st.cache_data(ttl=60)
    def _get_eventos_vida(_self) -> List[Dict]:
        """Obtém eventos de vida (com cache)."""
        if not _self.db:
            return []
        
        try:
            eventos = _self.db.get_eventos_vida()
            return eventos if isinstance(eventos, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar eventos de vida: {e}", exc_info=True)
            return []
    
    def _render_evento_item(self, evento: Dict[str, Any]) -> None:
        """Renderiza um item de evento."""
        tipo = evento.get("tipo", "marco")
        data = self._formatar_data(evento.get("data_evento", ""))
        titulo = evento.get("titulo", "Evento")
        descricao = evento.get("descricao", "")
        icon = TIPO_ICON.get(tipo, "📌")
        
        desc_html = (
            f'<div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.2rem;">'
            f'{descricao}</div>'
            if descricao else ""
        )
        
        st.markdown(
            f"""
            <div style="display: flex; gap: 0.8rem; align-items: flex-start;
                padding: 0.7rem 0; border-bottom: 1px solid var(--border-subtle);">
                <span style="font-size: 1.3rem; flex-shrink: 0;">{icon}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 0.92rem; color: var(--text);">
                        {titulo}
                    </div>
                    {desc_html}
                </div>
                <span style="font-size: 0.76rem; color: var(--text-faint); flex-shrink: 0;">
                    {data}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = JourneyStoryRenderer(services, user)
    renderer.render()
