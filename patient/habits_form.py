"""
Melshape — Hábitos: formulário de criação e sugestões por pilar.
"""
import streamlit as st
from typing import Dict, Any, List, Tuple
import logging

from services.habit_service import HabitService

logger = logging.getLogger("Melshape.HabitsForm")


# Constantes de categorias
CATEGORIAS = {
    "hidratacao": ("💧", "Hidratação"),
    "nutricao": ("🥩", "Nutrição"),
    "movimento": ("🚶", "Movimento"),
    "treino": ("🏋️", "Treino"),
    "sono": ("😴", "Sono"),
    "registro": ("✅", "Registro"),
    "suplementos": ("💊", "Suplementos"),
    "saude": ("🩺", "Saúde"),
    "medicamento": ("💉", "Medicamento"),
    "alimentacao": ("🍽️", "Alimentação"),
    "monitoramento": ("📊", "Monitoramento"),
    "geral": ("⭐", "Geral"),
}

# Constantes de frequência
FREQUENCIAS = {
    "daily": "Diário",
    "weekly": "Semanal",
}

# Limite de caracteres
MAX_NOME_LENGTH = 50
MAX_ICON_LENGTH = 2
MAX_SUGESTOES_EXIBIDAS = 3


class HabitsFormRenderer:
    """Renderer dedicado para formulário de hábitos."""
    
    def __init__(self, db, svc: HabitService):
        self.db = db
        self.svc = svc
    
    def render(self, health_mode: str) -> None:
        """Renderiza formulário de novo hábito."""
        st.markdown("##### ➕ Criar Novo Hábito")
        
        # Verifica limite de hábitos
        if not self._verificar_limite_habitos():
            return
        
        # Sugestões do pilar
        self._render_sugestoes(health_mode)
        
        st.markdown("---")
        st.markdown("**Ou crie um personalizado:**")
        
        # Formulário personalizado
        self._render_form_personalizado()
    
    def _verificar_limite_habitos(self) -> bool:
        """Verifica se usuário atingiu limite de hábitos."""
        try:
            habitos = self.db.get_habitos()
            total = len(habitos) if habitos else 0
            
            if total >= 20:
                st.warning(
                    "⚠️ Você atingiu o limite de 20 hábitos. "
                    "Exclua alguns para criar novos."
                )
                return False
            
            return True
        except Exception as e:
            logger.error(f"Erro ao verificar limite de hábitos: {e}", exc_info=True)
            return True  # Permite continuar em caso de erro
    
    def _render_sugestoes(self, health_mode: str) -> None:
        """Renderiza sugestões de hábitos do pilar."""
        sugestoes = self._get_sugestoes(health_mode)
        
        if not sugestoes:
            return
        
        st.markdown(
            """
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.6rem;">
                💡 <b>Sugestões para seu pilar:</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        num_cols = min(MAX_SUGESTOES_EXIBIDAS, len(sugestoes))
        cols = st.columns(num_cols)
        
        for i, sugestao in enumerate(sugestoes[:MAX_SUGESTOES_EXIBIDAS]):
            with cols[i % num_cols]:
                self._render_sugestao_item(i, sugestao)
    
    @st.cache_data(ttl=60)
    def _get_sugestoes(_self, health_mode: str) -> List[Tuple[str, str, str, str]]:
        """Obtém sugestões do pilar (com cache)."""
        try:
            sugestoes = _self.svc.sugestoes(health_mode)
            return sugestoes if isinstance(sugestoes, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter sugestões do pilar '{health_mode}': {e}", exc_info=True)
            return []
    
    def _render_sugestao_item(self, idx: int, sugestao: Tuple[str, str, str, str]) -> None:
        """Renderiza item de sugestão."""
        icone, nome, categoria, frequencia = sugestao
        
        # Trunca nome se muito longo
        nome_display = nome[:22] + "..." if len(nome) > 22 else nome
        
        if st.button(
            f"{icone} {nome_display}",
            key=f"sug_{idx}",
            use_container_width=True,
        ):
            self._criar_habito(nome, categoria, icone, frequencia)
    
    def _render_form_personalizado(self) -> None:
        """Renderiza formulário de hábito personalizado."""
        col1, col2 = st.columns([3, 1])
        
        with col1:
            nome = st.text_input(
                "Nome do hábito",
                placeholder="Ex: Meditar 10 minutos",
                max_chars=MAX_NOME_LENGTH,
                key="hab_nome",
            )
        
        with col2:
            icone = st.text_input(
                "Ícone",
                value="⭐",
                max_chars=MAX_ICON_LENGTH,
                key="hab_icone",
            )
        
        col3, col4 = st.columns(2)
        
        with col3:
            categoria = st.selectbox(
                "Categoria",
                list(CATEGORIAS.keys()),
                format_func=lambda k: f"{CATEGORIAS[k][0]} {CATEGORIAS[k][1]}",
                key="hab_cat",
            )
        
        with col4:
            frequencia = st.selectbox(
                "Frequência",
                list(FREQUENCIAS.keys()),
                format_func=lambda x: FREQUENCIAS[x],
                key="hab_freq",
            )
        
        if st.button(
            "✅ Criar hábito",
            type="primary",
            use_container_width=True,
            key="hab_criar",
        ):
            self._criar_habito_personalizado(nome, icone, categoria, frequencia)
    
    def _criar_habito_personalizado(
        self,
        nome: str,
        icone: str,
        categoria: str,
        frequencia: str,
    ) -> None:
        """Cria hábito personalizado com validações."""
        # Validações
        if not self._validar_nome(nome):
            return
        
        if not self._validar_icone(icone):
            return
        
        self._criar_habito(nome.strip(), categoria, icone.strip(), frequencia)
    
    def _validar_nome(self, nome: str) -> bool:
        """Valida nome do hábito."""
        if not nome or not nome.strip():
            st.warning("⚠️ Digite um nome para o hábito.")
            return False
        
        if len(nome.strip()) < 3:
            st.warning("⚠️ O nome deve ter pelo menos 3 caracteres.")
            return False
        
        return True
    
    def _validar_icone(self, icone: str) -> bool:
        """Valida ícone do hábito."""
        if not icone or not icone.strip():
            st.warning("⚠️ Digite um ícone (emoji) para o hábito.")
            return False
        
        return True
    
    def _criar_habito(
        self,
        nome: str,
        categoria: str,
        icone: str,
        frequencia: str,
    ) -> None:
        """Cria um novo hábito com tratamento de erros."""
        try:
            success = self.db.criar_habito(
                nome,
                categoria,
                icone,
                frequencia,
            )
            
            if success:
                self._processar_sucesso_criacao(nome, icone)
            else:
                st.error("❌ Erro ao criar hábito.")
        except Exception as e:
            logger.error(f"Erro ao criar hábito '{nome}': {e}", exc_info=True)
            st.error(f"❌ Erro ao criar hábito: {str(e)}")
    
    def _processar_sucesso_criacao(self, nome: str, icone: str) -> None:
        """Processa sucesso da criação de hábito."""
        st.toast(f"{icone} Hábito '{nome}' criado!", icon="✅")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()


# Função de compatibilidade
def _tab_novo(db, svc: HabitService, health_mode: str) -> None:
    """Renderiza tab de novo hábito (compatibilidade)."""
    renderer = HabitsFormRenderer(db, svc)
    renderer.render(health_mode)
