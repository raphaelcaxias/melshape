"""
Melshape — Formulários da Narrativa da Jornada.
Importado por journey_story.py.
"""
import streamlit as st
from typing import Dict, Any, Optional
from datetime import date
import logging

logger = logging.getLogger("Melshape.JourneyStoryForms")


# Constantes de tipos de evento
TIPOS_EVENTO = {
    "marco": "🏁 Marco alcançado",
    "celebracao": "🎉 Celebração",
    "desafio": "⚡ Superei um desafio",
    "dificuldade": "💪 Momento difícil superado",
    "inicio": "🌱 Início de algo novo",
}

# Constantes de validação
MIN_MOTIVO_LENGTH = 10
MIN_TITULO_LENGTH = 3
MAX_PESO = 300.0
MIN_PESO = 0.0


class JourneyStoryFormsRenderer:
    """Renderer para formulários da narrativa."""
    
    def __init__(self, db):
        self.db = db
    
    def render_motivo(self, jornada_id: str, has_motivo: bool = False) -> None:
        """Renderiza formulário de motivo."""
        label = "Adicionar outro motivo" if has_motivo else "Registrar meu porquê"
        st.markdown(f"**{label}**")
        
        motivo = st.text_area(
            "Motivo",
            height=90,
            placeholder=(
                "Ex: Quero ter energia para brincar com meus filhos. "
                "Quero me sentir bem ao me olhar no espelho. "
                "Quero controlar minha saúde antes que seja tarde."
            ),
            key="story_motivo",
            label_visibility="collapsed",
        )
        
        if st.button(
            "💛 Salvar meu porquê",
            type="primary",
            use_container_width=True,
            key="story_motivo_save",
        ):
            self._salvar_motivo(jornada_id, motivo)
    
    def _salvar_motivo(self, jornada_id: str, motivo: str) -> None:
        """Salva motivo com validações e tratamento de erros."""
        # Validação
        if not self._validar_motivo(motivo):
            return
        
        try:
            success = self.db.salvar_motivo(jornada_id, motivo.strip())
            
            if success:
                self._processar_sucesso_motivo()
            else:
                st.error("❌ Erro ao salvar motivo.")
        except Exception as e:
            logger.error(f"Erro ao salvar motivo: {e}", exc_info=True)
            st.error(f"❌ Erro ao salvar motivo: {str(e)}")
    
    def _validar_motivo(self, motivo: str) -> bool:
        """Valida motivo antes de salvar."""
        if not motivo or not motivo.strip():
            st.warning("⚠️ Escreva seu motivo.")
            return False
        
        if len(motivo.strip()) < MIN_MOTIVO_LENGTH:
            st.warning(f"⚠️ O motivo deve ter pelo menos {MIN_MOTIVO_LENGTH} caracteres.")
            return False
        
        return True
    
    def _processar_sucesso_motivo(self) -> None:
        """Processa sucesso do salvamento de motivo."""
        st.toast("💛 Motivo salvo!", icon="✅")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def render_foto(self, perfil_id: str, user: Dict[str, Any]) -> None:
        """Renderiza formulário de foto."""
        st.markdown("**📸 Registrar nova foto**")
        
        peso_padrao = self._extrair_peso_padrao(user)
        
        col1, col2 = st.columns(2)
        
        with col1:
            url_foto = st.text_input(
                "URL da foto (Google Drive, Imgur, etc.)",
                placeholder="https://...",
                key="story_foto_url",
            )
        
        with col2:
            peso_foto = st.number_input(
                "Peso nesta data (kg)",
                min_value=MIN_PESO,
                max_value=MAX_PESO,
                value=peso_padrao,
                step=0.1,
                key="story_foto_peso",
            )
        
        legenda = st.text_input(
            "Legenda (opcional)",
            placeholder="Ex: Início da jornada, 3 meses depois...",
            key="story_foto_leg",
        )
        
        self._render_dica_foto()
        
        if st.button(
            "📸 Registrar foto",
            use_container_width=True,
            key="story_foto_save",
        ):
            self._salvar_foto(perfil_id, url_foto, legenda, peso_foto)
    
    def _extrair_peso_padrao(self, user: Dict[str, Any]) -> float:
        """Extrai peso padrão do usuário de forma segura."""
        try:
            peso = user.get("current_weight")
            return float(peso) if peso is not None else 70.0
        except (ValueError, TypeError):
            return 70.0
    
    def _render_dica_foto(self) -> None:
        """Renderiza dica sobre hospedagem de fotos."""
        st.markdown(
            """
            <div style="font-size: 0.78rem; color: var(--text-muted); margin: 0.5rem 0;">
                💡 <b>Dica:</b> hospede no Google Fotos, Imgur ou Drive e cole o link direto.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _salvar_foto(
        self,
        perfil_id: str,
        url_foto: str,
        legenda: str,
        peso_foto: float,
    ) -> None:
        """Salva foto com validações e tratamento de erros."""
        # Validação
        if not self._validar_url_foto(url_foto):
            return
        
        try:
            success = self.db.salvar_foto(
                perfil_id,
                url_foto.strip(),
                legenda,
                peso_foto,
            )
            
            if success:
                self._processar_sucesso_foto()
            else:
                st.error("❌ Erro ao salvar foto.")
        except Exception as e:
            logger.error(f"Erro ao salvar foto: {e}", exc_info=True)
            st.error(f"❌ Erro ao salvar foto: {str(e)}")
    
    def _validar_url_foto(self, url: str) -> bool:
        """Valida URL da foto."""
        if not url or not url.strip():
            st.warning("⚠️ Cole a URL da foto.")
            return False
        
        if not url.strip().startswith("http"):
            st.warning("⚠️ A URL deve começar com http:// ou https://")
            return False
        
        return True
    
    def _processar_sucesso_foto(self) -> None:
        """Processa sucesso do salvamento de foto."""
        st.toast("📸 Foto registrada!", icon="✅")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def render_evento(self) -> None:
        """Renderiza formulário de evento."""
        st.markdown("**📅 Registrar momento**")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            tipo = st.selectbox(
                "Tipo",
                list(TIPOS_EVENTO.keys()),
                format_func=lambda k: TIPOS_EVENTO[k],
                key="ev_tipo",
                label_visibility="collapsed",
            )
        
        with col2:
            titulo = st.text_input(
                "Título",
                placeholder="Ex: Completei minha primeira semana",
                key="ev_titulo",
                label_visibility="collapsed",
            )
        
        descricao = st.text_area(
            "Como foi? (opcional)",
            height=70,
            key="ev_desc",
            placeholder="Descreva como se sentiu...",
            label_visibility="collapsed",
        )
        
        if st.button(
            "📅 Salvar momento",
            use_container_width=True,
            key="ev_save",
        ):
            self._salvar_evento(titulo, descricao, tipo)
    
    def _salvar_evento(self, titulo: str, descricao: str, tipo: str) -> None:
        """Salva evento com validações e tratamento de erros."""
        # Validação
        if not self._validar_titulo_evento(titulo):
            return
        
        try:
            success = self.db.registrar_evento_vida(
                titulo.strip(),
                descricao,
                tipo,
            )
            
            if success:
                self._processar_sucesso_evento()
            else:
                st.error("❌ Erro ao salvar momento.")
        except Exception as e:
            logger.error(f"Erro ao salvar evento: {e}", exc_info=True)
            st.error(f"❌ Erro ao salvar momento: {str(e)}")
    
    def _validar_titulo_evento(self, titulo: str) -> bool:
        """Valida título do evento."""
        if not titulo or not titulo.strip():
            st.warning("⚠️ Dê um título ao momento.")
            return False
        
        if len(titulo.strip()) < MIN_TITULO_LENGTH:
            st.warning(f"⚠️ O título deve ter pelo menos {MIN_TITULO_LENGTH} caracteres.")
            return False
        
        return True
    
    def _processar_sucesso_evento(self) -> None:
        """Processa sucesso do salvamento de evento."""
        st.toast("📅 Momento registrado!", icon="✅")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()


# Funções de compatibilidade
def render_form_motivo(db, jornada_id: str, has_motivo: bool = False) -> None:
    """Renderiza formulário de motivo (compatibilidade)."""
    renderer = JourneyStoryFormsRenderer(db)
    renderer.render_motivo(jornada_id, has_motivo)


def render_form_foto(db, perfil_id: str, user: Dict[str, Any]) -> None:
    """Renderiza formulário de foto (compatibilidade)."""
    renderer = JourneyStoryFormsRenderer(db)
    renderer.render_foto(perfil_id, user)


def render_form_evento(db) -> None:
    """Renderiza formulário de evento (compatibilidade)."""
    renderer = JourneyStoryFormsRenderer(db)
    renderer.render_evento()
