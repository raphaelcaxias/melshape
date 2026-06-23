"""
Melshape — Ações do Profissional sobre o Paciente.

O profissional não apenas observa — age.
Registra condutas, observações e prescrições diretamente no sistema.

Princípio: toda informação deve responder
"O que devo fazer com este paciente agora?"
"""
import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from views.components.cards import empty_state, alert, divider
from views.professional.patient_prescription import _tab_prescricao
from services.clinical_loop import ClinicalLoopService

logger = logging.getLogger("Melshape.PatientActions")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Tipos de conduta
TIPOS_CONDUTA = {
    "orientacao": "📋 Orientação",
    "ajuste_dieta": "🥗 Ajuste de Dieta",
    "alerta": "⚠️ Alerta Clínico",
    "encaminhamento": "🏥 Encaminhamento",
    "elogio": "🌟 Reconhecimento",
    "revisao": "🔄 Revisão de Protocolo",
}

# Limites de exibição
MAX_CONDUTAS_EXIBIR = 3
MAX_OBSERVACOES_EXIBIR = 5

# Fallbacks
DEFAULT_NOME = "—"
DEFAULT_TIPO_CONDUTA = "orientacao"
DEFAULT_PROFissional = ""


@dataclass
class CondutaData:
    """Dados de uma conduta."""
    titulo: str = ""
    tipo: str = DEFAULT_TIPO_CONDUTA
    descricao: str = ""


class PatientActionsRenderer:
    """Renderer dedicado para ações do profissional."""
    
    def __init__(self, services: Dict[str, Any], professional, paciente: Dict[str, Any]):
        self.services = services or {}
        self.professional = professional
        self.paciente = paciente or {}
        self.db = services.get("db")
        self.perfil_id = self._get_perfil_id()
        self.nome = self._get_nome_paciente()
    
    def _get_perfil_id(self) -> str:
        """Obtém ID do perfil com tratamento de erros."""
        try:
            return self.paciente.get("id", "")
        except Exception as e:
            logger.error(f"Erro ao obter perfil ID: {e}", exc_info=True)
            return ""
    
    def _get_nome_paciente(self) -> str:
        """Obtém nome do paciente com tratamento de erros."""
        try:
            return self.paciente.get("nome_completo", DEFAULT_NOME)
        except Exception as e:
            logger.error(f"Erro ao obter nome do paciente: {e}", exc_info=True)
            return DEFAULT_NOME
    
    def render(self) -> None:
        """Renderiza ações do profissional com tratamento de erros."""
        try:
            # Tabs
            self._render_tabs()
        except Exception as e:
            logger.error(f"Erro ao renderizar ações do profissional: {e}", exc_info=True)
            st.error("❌ Erro ao carregar ações do profissional.")
    
    def _render_tabs(self) -> None:
        """Renderiza as 3 tabs de ações."""
        tab_conduta, tab_obs, tab_presc = st.tabs([
            "📋 Conduta",
            "📝 Observação",
            "🥗 Prescrição",
        ])
        
        with tab_conduta:
            self._render_tab_conduta()
        
        with tab_obs:
            self._render_tab_observacao()
        
        with tab_presc:
            self._render_tab_prescricao()
    
    def _render_tab_conduta(self) -> None:
        """Renderiza tab de conduta com tratamento de erros."""
        try:
            self._render_conduta()
        except Exception as e:
            logger.error(f"Erro ao renderizar tab conduta: {e}", exc_info=True)
            alert("❌ Erro ao carregar condutas.", "error")
    
    def _render_tab_observacao(self) -> None:
        """Renderiza tab de observação com tratamento de erros."""
        try:
            self._render_observacao()
        except Exception as e:
            logger.error(f"Erro ao renderizar tab observação: {e}", exc_info=True)
            alert("❌ Erro ao carregar observações.", "error")
    
    def _render_tab_prescricao(self) -> None:
        """Renderiza tab de prescrição com tratamento de erros."""
        try:
            _tab_prescricao(self.db, self.perfil_id, self.nome)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab prescrição: {e}", exc_info=True)
            alert("❌ Erro ao carregar prescrições.", "error")
    
    def _render_conduta(self) -> None:
        """Renderiza tab de conduta."""
        st.markdown(f"##### 📋 Conduta para {self.nome}")
        
        # Condutas existentes
        condutas = self._get_condutas()
        
        if condutas:
            self._render_header_condutas(len(condutas))
            
            for conduta in condutas[:MAX_CONDUTAS_EXIBIR]:
                self._render_conduta_item(conduta)
        
        divider()
        
        # Nova conduta
        self._render_form_conduta()
    
    @st.cache_data(ttl=60)
    def _get_condutas(_self) -> List[Dict]:
        """Obtém condutas do paciente (com cache)."""
        if not _self.db or not _self.perfil_id:
            return []
        
        try:
            condutas = _self.db.get_condutas(_self.perfil_id)
            return condutas if isinstance(condutas, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter condutas: {e}", exc_info=True)
            return []
    
    def _render_header_condutas(self, total: int) -> None:
        """Renderiza cabeçalho de condutas."""
        st.markdown(
            f"""
            <div style="font-size: 0.80rem; color: var(--text-muted); margin-bottom: 0.6rem;">
                <b>{total}</b> conduta(s) registrada(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_conduta_item(self, conduta: Dict) -> None:
        """Renderiza um item de conduta com tratamento de erros."""
        try:
            if not isinstance(conduta, dict):
                return
            
            tipo = conduta.get("tipo", DEFAULT_TIPO_CONDUTA)
            label = TIPOS_CONDUTA.get(tipo, tipo)
            data = self._formatar_data(conduta.get("data_conduta", ""))
            titulo = conduta.get("titulo", "")
            descricao = conduta.get("descricao", "")
            
            desc_html = (
                f'<div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.2rem;">'
                f'{descricao}</div>'
                if descricao else ""
            )
            
            st.markdown(
                f"""
                <div style="padding: 0.6rem 0.8rem; border-left: 3px solid
                    var(--primary); margin-bottom: 0.5rem; background: var(--surface-2);
                    border-radius: 0 8px 8px 0;">
                    <div style="font-size: 0.78rem; color: var(--text-muted);">
                        {label} · {data}
                    </div>
                    <div style="font-size: 0.90rem; color: var(--text); font-weight: 600; margin-top: 0.2rem;">
                        {titulo}
                    </div>
                    {desc_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar conduta item: {e}", exc_info=True)
    
    def _formatar_data(self, data_raw: Any) -> str:
        """Formata data de forma segura."""
        try:
            if not data_raw:
                return "—"
            return str(data_raw)[:10]
        except Exception as e:
            logger.debug(f"Erro ao formatar data: {e}")
            return "—"
    
    def _render_form_conduta(self) -> None:
        """Renderiza formulário de nova conduta."""
        data = CondutaData()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            data.titulo = st.text_input(
                "Título da conduta",
                placeholder="Ex: Aumentar proteína para 1.8g/kg",
                key=f"cond_titulo_{self.perfil_id}",
            )
        
        with col2:
            data.tipo = st.selectbox(
                "Tipo",
                list(TIPOS_CONDUTA.keys()),
                format_func=lambda k: TIPOS_CONDUTA[k],
                key=f"cond_tipo_{self.perfil_id}",
            )
        
        data.descricao = st.text_area(
            "Detalhes (opcional)",
            height=80,
            placeholder="Orientações, justificativa, próximos passos...",
            key=f"cond_desc_{self.perfil_id}",
        )
        
        if st.button(
            "📋 Registrar conduta",
            type="primary",
            use_container_width=True,
            key=f"cond_save_{self.perfil_id}",
        ):
            self._salvar_conduta(data)
    
    def _salvar_conduta(self, data: CondutaData) -> None:
        """Salva uma nova conduta com validações."""
        # Validações
        if not self._validar_conduta(data):
            return
        
        try:
            success = self.db.registrar_conduta(
                self.perfil_id,
                data.titulo.strip(),
                data.descricao,
                data.tipo,
            )
            
            if success:
                self._processar_sucesso_conduta(data)
            else:
                st.error("❌ Erro ao registrar conduta.")
        except Exception as e:
            logger.error(f"Erro ao salvar conduta: {e}", exc_info=True)
            st.error(f"❌ Erro ao registrar conduta: {str(e)}")
    
    def _validar_conduta(self, data: CondutaData) -> bool:
        """Valida dados da conduta."""
        if not data.titulo or not data.titulo.strip():
            st.warning("⚠️ Digite um título para a conduta.")
            return False
        
        return True
    
    def _processar_sucesso_conduta(self, data: CondutaData) -> None:
        """Processa sucesso do registro de conduta."""
        # Fecha o loop clínico
        self._fechar_loop_clinico(data)
        
        st.toast("📋 Conduta registrada — paciente notificado!", icon="✅")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def _fechar_loop_clinico(self, data: CondutaData) -> None:
        """Fecha o loop clínico após conduta."""
        try:
            pro_nome = self._get_professional_name()
            ClinicalLoopService(self.db).apos_conduta(
                self.perfil_id,
                data.titulo.strip(),
                data.descricao,
                data.tipo,
                pro_nome,
            )
        except Exception as e:
            logger.error(f"Erro ao fechar loop clínico: {e}", exc_info=True)
            # Não raise, pois não é crítico
    
    def _get_professional_name(self) -> str:
        """Obtém nome do profissional com tratamento de erros."""
        try:
            pro = st.session_state.get("professional")
            
            if not pro:
                return DEFAULT_PROFissional
            
            if hasattr(pro, "name"):
                return pro.name or DEFAULT_PROFissional
            
            if isinstance(pro, dict):
                return pro.get("name", DEFAULT_PROFissional)
            
            return DEFAULT_PROFissional
        except Exception as e:
            logger.error(f"Erro ao obter nome do profissional: {e}", exc_info=True)
            return DEFAULT_PROFissional
    
    def _render_observacao(self) -> None:
        """Renderiza tab de observação."""
        st.markdown(f"##### 📝 Observações sobre {self.nome}")
        
        # Observações existentes
        observacoes = self._get_observacoes()
        
        if observacoes:
            for obs in observacoes[:MAX_OBSERVACOES_EXIBIR]:
                self._render_observacao_item(obs)
        else:
            empty_state("📝", "Nenhuma observação ainda")
        
        divider()
        
        # Nova observação
        self._render_form_observacao()
    
    @st.cache_data(ttl=60)
    def _get_observacoes(_self) -> List[Dict]:
        """Obtém observações do paciente (com cache)."""
        if not _self.db or not _self.perfil_id:
            return []
        
        try:
            observacoes = _self.db.get_observacoes(_self.perfil_id)
            return observacoes if isinstance(observacoes, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter observações: {e}", exc_info=True)
            return []
    
    def _render_observacao_item(self, observacao: Dict) -> None:
        """Renderiza um item de observação com tratamento de erros."""
        try:
            if not isinstance(observacao, dict):
                return
            
            data = self._formatar_data(observacao.get("criado_em", ""))
            privada = "🔒" if observacao.get("privada") else "👁️"
            texto = observacao.get("observacao", "")
            
            st.markdown(
                f"""
                <div style="padding: 0.6rem 0; border-bottom: 1px solid var(--border-subtle);">
                    <div style="font-size: 0.76rem; color: var(--text-faint);">
                        {privada} {data}
                    </div>
                    <div style="font-size: 0.88rem; color: var(--text); margin-top: 0.2rem;">
                        {texto}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar observação item: {e}", exc_info=True)
    
    def _render_form_observacao(self) -> None:
        """Renderiza formulário de nova observação."""
        obs_texto = st.text_area(
            "Nova observação",
            height=100,
            placeholder="Anotação clínica, comportamental ou motivacional...",
            key=f"obs_texto_{self.perfil_id}",
        )
        
        privada = st.checkbox(
            "Observação privada (visível só para você)",
            value=True,
            key=f"obs_priv_{self.perfil_id}",
        )
        
        if st.button(
            "📝 Salvar observação",
            type="primary",
            use_container_width=True,
            key=f"obs_save_{self.perfil_id}",
        ):
            self._salvar_observacao(obs_texto, privada)
    
    def _salvar_observacao(self, texto: str, privada: bool) -> None:
        """Salva uma observação com validações."""
        # Validações
        if not self._validar_observacao(texto):
            return
        
        try:
            success = self.db.registrar_observacao(
                self.perfil_id,
                texto.strip(),
                privada,
            )
            
            if success:
                self._processar_sucesso_observacao()
            else:
                st.error("❌ Erro ao salvar observação.")
        except Exception as e:
            logger.error(f"Erro ao salvar observação: {e}", exc_info=True)
            st.error(f"❌ Erro ao salvar observação: {str(e)}")
    
    def _validar_observacao(self, texto: str) -> bool:
        """Valida observação."""
        if not texto or not texto.strip():
            st.warning("⚠️ Digite a observação.")
            return False
        
        return True
    
    def _processar_sucesso_observacao(self) -> None:
        """Processa sucesso do salvamento de observação."""
        st.toast("📝 Observação salva!", icon="✅")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()


# Função principal de compatibilidade
def render(services: Dict[str, Any], professional, paciente: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = PatientActionsRenderer(services, professional, paciente)
    renderer.render()
