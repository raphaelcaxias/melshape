"""
Melshape — Metas: formulário de criação guiada.
Templates por tipo, vincula automaticamente à jornada ativa.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Tuple
from datetime import date
import logging

from services.goals_service import GoalsService

logger = logging.getLogger("Melshape.GoalsForm")


class GoalsFormRenderer:
    """Renderer dedicado para formulário de metas."""
    
    # Constantes de explicações por tipo
    EXPLICACOES_TIPOS = {
        "peso": (
            "📊 Progresso calculado automaticamente "
            "comparando seu peso inicial com o atual."
        ),
        "habito": (
            "📋 Progresso baseado nos dias que você "
            "registrou pelo menos 1 hábito."
        ),
        "consistencia": (
            "🔥 Progresso = sua sequência atual de check-ins."
        ),
        "agua": (
            "💧 Conta os dias em que você atingiu 2L de água."
        ),
        "proteina": (
            "🥩 Compara sua média de proteína (7d) com o alvo."
        ),
        "livre": (
            "🎯 Você controla o progresso manualmente."
        ),
    }
    
    # Constantes de valores padrão
    VALOR_ALVO_PADRAO = 10.0
    UNIDADE_PADRAO = "unidades"
    
    def __init__(self, db, svc: GoalsService):
        self.db = db
        self.svc = svc
    
    def render(self, jornada_id: str, health_mode: str) -> None:
        """Renderiza formulário de nova meta."""
        st.markdown("##### ➕ Nova Meta")
        
        if not jornada_id:
            st.warning("⚠️ Você precisa ter uma jornada ativa para criar metas.")
            return
        
        # Seleção de tipo e template
        tipo_selecionado, template = self._render_tipo_selecao()
        
        # Campos do formulário
        titulo, valor_alvo, unidade, prazo = self._render_campos(template)
        
        # Explicação do tipo
        self._render_explicacao(tipo_selecionado)
        
        # Botão de criação
        if st.button(
            "✅ Criar meta",
            type="primary",
            use_container_width=True,
            key="goal_criar",
        ):
            self._criar_meta(
                jornada_id, tipo_selecionado, titulo,
                valor_alvo, unidade, prazo
            )
    
    def _render_tipo_selecao(self) -> Tuple[str, Dict[str, Any]]:
        """Renderiza seleção de tipo e template."""
        tipo_labels = self._get_tipo_labels()
        tipos = list(tipo_labels.keys())
        
        if not tipos:
            st.error("❌ Não foi possível carregar tipos de meta.")
            return "livre", {}
        
        col1, col2 = st.columns(2)
        
        with col1:
            tipo_selecionado = st.selectbox(
                "Tipo de meta",
                tipos,
                format_func=lambda k: self._format_tipo_label(k, tipo_labels),
                key="goal_tipo",
            )
        
        with col2:
            template, is_custom = self._render_template_select(tipo_selecionado)
        
        return tipo_selecionado, template
    
    def _get_tipo_labels(self) -> Dict[str, Tuple[str, str]]:
        """Obtém labels de tipos com tratamento de erros."""
        try:
            return self.svc.tipo_labels()
        except Exception as e:
            logger.error(f"Erro ao obter tipo labels: {e}", exc_info=True)
            return {"livre": ("🎯", "Livre")}
    
    def _format_tipo_label(self, tipo: str, tipo_labels: Dict) -> str:
        """Formata label do tipo de forma segura."""
        try:
            icone, label = tipo_labels.get(tipo, ("🎯", tipo))
            return f"{icone} {label}"
        except Exception as e:
            logger.debug(f"Erro ao formatar label do tipo '{tipo}': {e}")
            return tipo
    
    def _render_template_select(self, tipo: str) -> Tuple[Dict[str, Any], bool]:
        """Renderiza seleção de template."""
        templates = self._get_templates(tipo)
        nomes_template = [t.get("titulo", "Template") for t in templates] + ["Personalizado"]
        
        template_idx = st.selectbox(
            "Template",
            range(len(nomes_template)),
            format_func=lambda i: nomes_template[i],
            key="goal_tmpl",
        )
        
        is_custom = template_idx >= len(templates)
        template = templates[template_idx] if not is_custom else {}
        
        return template, is_custom
    
    @st.cache_data(ttl=60)
    def _get_templates(_self, tipo: str) -> List[Dict]:
        """Obtém templates do tipo (com cache)."""
        try:
            templates = _self.svc.templates().get(tipo, [])
            return templates if isinstance(templates, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter templates do tipo '{tipo}': {e}", exc_info=True)
            return []
    
    def _render_campos(self, template: Dict[str, Any]) -> Tuple[str, float, str, Optional[date]]:
        """Renderiza campos do formulário."""
        defaults = self._extrair_defaults(template)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            titulo = st.text_input(
                "Título da meta",
                value=defaults["titulo"],
                key="goal_titulo",
            )
        
        with col2:
            prazo = st.date_input(
                "Prazo (opcional)",
                value=None,
                key="goal_prazo",
            )
        
        col3, col4 = st.columns(2)
        
        with col3:
            valor_alvo = st.number_input(
                "Valor alvo",
                min_value=0.1,
                value=defaults["valor_alvo"],
                step=0.5,
                key="goal_alvo",
            )
        
        with col4:
            unidade = st.text_input(
                "Unidade",
                value=defaults["unidade"],
                key="goal_unidade",
            )
        
        return titulo, valor_alvo, unidade, prazo
    
    def _extrair_defaults(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai valores padrão do template de forma segura."""
        try:
            return {
                "titulo": template.get("titulo", ""),
                "valor_alvo": self._parse_valor_alvo(template.get("valor_alvo")),
                "unidade": template.get("unidade", self.UNIDADE_PADRAO),
            }
        except Exception as e:
            logger.warning(f"Erro ao extrair defaults do template: {e}")
            return {
                "titulo": "",
                "valor_alvo": self.VALOR_ALVO_PADRAO,
                "unidade": self.UNIDADE_PADRAO,
            }
    
    def _parse_valor_alvo(self, valor_raw: Any) -> float:
        """Parse valor alvo de forma segura."""
        try:
            valor = float(valor_raw) if valor_raw is not None else self.VALOR_ALVO_PADRAO
            return max(0.1, valor)
        except (ValueError, TypeError):
            return self.VALOR_ALVO_PADRAO
    
    def _render_explicacao(self, tipo: str) -> None:
        """Renderiza explicação do tipo de meta."""
        mensagem = self.EXPLICACOES_TIPOS.get(tipo, "")
        
        if not mensagem:
            return
        
        st.markdown(
            f"""
            <div style="font-size: 0.82rem; color: var(--text-muted);
                background: var(--surface-2); padding: 0.6rem 0.9rem;
                border-radius: 8px; margin: 0.5rem 0;">
                {mensagem}
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _criar_meta(
        self,
        jornada_id: str,
        tipo: str,
        titulo: str,
        valor_alvo: float,
        unidade: str,
        prazo: Optional[date],
    ) -> None:
        """Cria uma nova meta com validações."""
        # Validações
        if not self._validar_titulo(titulo):
            return
        
        prazo_str = self._formatar_prazo(prazo)
        
        # Cria a meta
        try:
            success = self.db.criar_meta(
                jornada_id=jornada_id,
                titulo=titulo.strip(),
                valor_alvo=valor_alvo,
                unidade=unidade.strip(),
                prazo=prazo_str,
            )
            
            if success:
                self._processar_sucesso_criacao(jornada_id, titulo.strip(), tipo)
            else:
                st.error("❌ Erro ao criar meta.")
        except Exception as e:
            logger.error(f"Erro ao criar meta: {e}", exc_info=True)
            st.error(f"❌ Erro ao criar meta: {str(e)}")
    
    def _validar_titulo(self, titulo: str) -> bool:
        """Valida título da meta."""
        if not titulo or not titulo.strip():
            st.warning("⚠️ Digite um título para a meta.")
            return False
        return True
    
    def _formatar_prazo(self, prazo: Optional[date]) -> str:
        """Formata prazo de forma segura."""
        if not prazo:
            return ""
        
        try:
            return prazo.isoformat()
        except Exception as e:
            logger.warning(f"Erro ao formatar prazo: {e}")
            return ""
    
    def _processar_sucesso_criacao(self, jornada_id: str, titulo: str, tipo: str) -> None:
        """Processa sucesso da criação de meta."""
        # Atualiza o tipo da meta
        self._atualizar_tipo_meta(jornada_id, titulo, tipo)
        
        st.toast(f"🎯 Meta '{titulo}' criada!", icon="✅")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def _atualizar_tipo_meta(self, jornada_id: str, titulo: str, tipo: str) -> None:
        """Atualiza o tipo da meta no banco."""
        if not self._is_real_db():
            return
        
        try:
            meta_id = self._buscar_ultima_meta_id(jornada_id, titulo)
            
            if meta_id:
                self._atualizar_tipo_no_banco(meta_id, tipo)
        except Exception as e:
            logger.error(f"Erro ao atualizar tipo da meta: {e}", exc_info=True)
    
    def _is_real_db(self) -> bool:
        """Verifica se o banco é real (não mock)."""
        return (
            hasattr(self.db, "is_real") and
            self.db.is_real and
            hasattr(self.db, "client")
        )
    
    def _buscar_ultima_meta_id(self, jornada_id: str, titulo: str) -> Optional[str]:
        """Busca ID da última meta criada."""
        try:
            response = (
                self.db.client
                .table("metas")
                .select("id")
                .eq("jornada_id", jornada_id)
                .eq("titulo", titulo)
                .order("criado_em", desc=True)
                .limit(1)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                return response.data[0].get("id")
            
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar última meta: {e}")
            return None
    
    def _atualizar_tipo_no_banco(self, meta_id: str, tipo: str) -> None:
        """Atualiza tipo no banco de dados."""
        try:
            self.db.client.table("metas").update(
                {"tipo": tipo}
            ).eq("id", meta_id).execute()
        except Exception as e:
            logger.error(f"Erro ao atualizar tipo da meta {meta_id}: {e}")


# Função de compatibilidade
def render_form_meta(db, svc: GoalsService, jornada_id: str,
                      health_mode: str) -> None:
    """Renderiza formulário de meta (compatibilidade)."""
    renderer = GoalsFormRenderer(db, svc)
    renderer.render(jornada_id, health_mode)
