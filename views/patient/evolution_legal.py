"""
Melshape — Evolução: aba legal (consentimentos LGPD).
"""
import streamlit as st
from typing import Dict, Any, List, Optional
import logging

from services.evolution_service import EvolutionService
from views.components.cards import alert

logger = logging.getLogger("Melshape.Legal")


class LegalRenderer:
    """Renderer dedicado para aba legal."""
    
    # Constantes
    MAX_CONSENTIMENTOS_EXPANDER = 3
    VERSAO_TERMO = "2.0"
    TIPO_TERMO = "lgpd"
    
    def __init__(self, svc: EvolutionService):
        self.svc = svc
    
    def render(self) -> None:
        """Renderiza aba legal."""
        st.markdown("##### ⚖️ Consentimentos LGPD")
        
        consentimentos = self._get_consentimentos()
        ativos = self._filtrar_ativos(consentimentos)
        revogados = self._filtrar_revogados(consentimentos)
        
        # Consentimentos ativos
        if ativos:
            self._render_consentimentos_ativos(ativos)
        else:
            self._render_alerta_sem_consentimento()
        
        # Consentimentos revogados
        if revogados:
            self._render_info_revogados(len(revogados))
        
        # Termos
        self._render_termos()
        
        # Botão de assinar (se não tiver ativo)
        if not ativos:
            self._render_assinar_consentimento()
        else:
            self._render_info_termos_vigentes()
    
    @st.cache_data(ttl=60)
    def _get_consentimentos(_self) -> List[Dict]:
        """Obtém lista de consentimentos (com cache)."""
        try:
            consentimentos = _self.svc.get_consentimentos()
            return consentimentos or []
        except Exception as e:
            logger.error(f"Erro ao buscar consentimentos: {e}", exc_info=True)
            return []
    
    def _filtrar_ativos(self, consentimentos: List[Dict]) -> List[Dict]:
        """Filtra consentimentos ativos."""
        try:
            return [c for c in consentimentos if not c.get("revogado")]
        except Exception as e:
            logger.warning(f"Erro ao filtrar consentimentos ativos: {e}")
            return []
    
    def _filtrar_revogados(self, consentimentos: List[Dict]) -> List[Dict]:
        """Filtra consentimentos revogados."""
        try:
            return [c for c in consentimentos if c.get("revogado")]
        except Exception as e:
            logger.warning(f"Erro ao filtrar consentimentos revogados: {e}")
            return []
    
    def _render_alerta_sem_consentimento(self) -> None:
        """Renderiza alerta quando não há consentimento ativo."""
        alert(
            "⚠️ Você ainda não assinou os termos de consentimento LGPD. "
            "Leia e assine abaixo para continuar usando o MelShape.",
            "warning",
        )
    
    def _render_info_revogados(self, total: int) -> None:
        """Renderiza informação sobre consentimentos revogados."""
        st.markdown(
            f"""
            <div style="font-size: 0.78rem; color: var(--text-muted);
                margin-top: 0.5rem;">
                🔒 {total} consentimento(s) revogado(s) anteriormente.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_info_termos_vigentes(self) -> None:
        """Renderiza informação sobre termos vigentes."""
        st.markdown(
            """
            <div style="font-size: 0.80rem; color: var(--text-muted);
                margin-top: 0.5rem;">
                ✅ Termos vigentes assinados.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_consentimentos_ativos(self, ativos: List[Dict]) -> None:
        """Renderiza consentimentos ativos."""
        if not ativos:
            return
        
        ultimo = ativos[0]
        self._render_ultimo_consentimento(ultimo)
        
        # Gerenciar consentimentos
        with st.expander("🔒 Gerenciar consentimentos"):
            for consentimento in ativos[:self.MAX_CONSENTIMENTOS_EXPANDER]:
                self._render_consentimento_item(consentimento)
    
    def _render_ultimo_consentimento(self, consentimento: Dict[str, Any]) -> None:
        """Renderiza informações do último consentimento."""
        data = self._formatar_data(consentimento.get("assinado_em"))
        versao = consentimento.get("versao", "—")
        tipo = consentimento.get("tipo", "—")
        
        st.markdown(
            f"""
            <div class="alert-success" style="margin-bottom: 0.6rem;">
                ✅ Você assinou os termos em <b>{data}</b><br>
                <small style="font-size: 0.76rem; color: var(--text-muted);">
                    Versão: {versao} · Tipo: {tipo}
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _formatar_data(self, data_raw: Any) -> str:
        """Formata data de forma segura."""
        if not data_raw:
            return "—"
        
        try:
            data_str = str(data_raw)[:10]
            if len(data_str) == 10 and data_str[4] == "-" and data_str[7] == "-":
                ano, mes, dia = data_str.split("-")
                return f"{dia}/{mes}/{ano}"
            return data_str
        except Exception as e:
            logger.debug(f"Erro ao formatar data '{data_raw}': {e}")
            return str(data_raw)[:10] if data_raw else "—"
    
    def _render_consentimento_item(self, consentimento: Dict[str, Any]) -> None:
        """Renderiza um item de consentimento com confirmação de revogação."""
        consentimento_id = consentimento.get("id", "")
        
        if not consentimento_id:
            logger.warning("Consentimento sem ID encontrado")
            return
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            self._render_info_consentimento(consentimento)
        
        with col2:
            self._render_botao_revogar(consentimento_id)
    
    def _render_info_consentimento(self, consentimento: Dict[str, Any]) -> None:
        """Renderiza informações do consentimento."""
        data = self._formatar_data(consentimento.get("assinado_em"))
        tipo = consentimento.get("tipo", "")
        versao = consentimento.get("versao", "")
        
        st.markdown(
            f"""
            <div style="font-size: 0.82rem; color: var(--text); padding: 0.3rem 0;">
                {data} — {tipo} v{versao}
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_botao_revogar(self, consentimento_id: str) -> None:
        """Renderiza botão de revogar com confirmação."""
        # Verifica se já está em modo de confirmação
        confirm_key = f"confirm_rev_{consentimento_id}"
        
        if st.session_state.get(confirm_key):
            # Modo de confirmação
            col_conf1, col_conf2 = st.columns(2)
            
            with col_conf1:
                if st.button(
                    "❌ Cancelar",
                    key=f"cancel_rev_{consentimento_id}",
                    use_container_width=True,
                ):
                    st.session_state[confirm_key] = False
                    st.rerun()
            
            with col_conf2:
                if st.button(
                    "✅ Confirmar",
                    key=f"confirm_rev_btn_{consentimento_id}",
                    type="primary",
                    use_container_width=True,
                ):
                    self._revogar_consentimento(consentimento_id)
                    st.session_state[confirm_key] = False
        else:
            # Botão inicial
            if st.button(
                "Revogar",
                key=f"rev_{consentimento_id}",
                help="Revogar este consentimento",
                use_container_width=True,
            ):
                st.session_state[confirm_key] = True
                st.rerun()
    
    def _revogar_consentimento(self, consentimento_id: str) -> None:
        """Revoga consentimento com tratamento de erros."""
        try:
            success = self.svc.revogar_consentimento(consentimento_id)
            
            if success:
                st.toast("🔒 Consentimento revogado com sucesso.", icon="✅")
                st.cache_data.clear()  # Limpa cache para atualizar dados
                st.rerun()
            else:
                st.error("❌ Erro ao revogar consentimento.")
        except Exception as e:
            logger.error(f"Erro ao revogar consentimento {consentimento_id}: {e}", exc_info=True)
            st.error(f"❌ Erro ao revogar consentimento: {str(e)}")
    
    def _render_termos(self) -> None:
        """Renderiza termos de consentimento."""
        st.markdown("---")
        
        with st.expander("📄 Ler Termos de Consentimento LGPD"):
            st.markdown(self._get_texto_termos())
    
    def _get_texto_termos(self) -> str:
        """Retorna texto dos termos de consentimento."""
        return f"""
**Declaração de Consentimento — MelShape v{self.VERSAO_TERMO}**

Ao assinar, você autoriza o MelShape a coletar, armazenar e processar
seus dados pessoais de saúde para fins de acompanhamento da sua
jornada de transformação, conforme a Lei Geral de Proteção de Dados
(Lei 13.709/2018).

**Dados coletados:** peso, medidas, refeições, check-ins,
humor, energia, sono, exames clínicos e fotos de evolução.

**Seus direitos (Art. 18 LGPD):**
- Acessar seus dados a qualquer momento
- Solicitar correção ou exclusão
- Revogar este consentimento (dados serão anonimizados em 30 dias)
- Portabilidade dos dados

**Responsável:** MelShape · suporte@melshape.com.br  
**Versão:** {self.VERSAO_TERMO} · Vigência: 01/01/2025
        """
    
    def _render_assinar_consentimento(self) -> None:
        """Renderiza botão para assinar consentimento."""
        if st.button(
            "✍️ Assinar consentimento",
            type="primary",
            use_container_width=True,
            key="ev_assinar",
        ):
            self._assinar_consentimento()
    
    def _assinar_consentimento(self) -> None:
        """Assina consentimento com tratamento de erros."""
        try:
            success = self.svc.assinar_consentimento(self.TIPO_TERMO, self.VERSAO_TERMO)
            
            if success:
                st.toast("⚖️ Consentimento assinado com sucesso!", icon="✅")
                st.cache_data.clear()  # Limpa cache para atualizar dados
                st.rerun()
            else:
                st.error("❌ Erro ao assinar consentimento.")
        except Exception as e:
            logger.error(f"Erro ao assinar consentimento: {e}", exc_info=True)
            st.error(f"❌ Erro ao assinar consentimento: {str(e)}")


# Função de compatibilidade
def _tab_legal(svc: EvolutionService) -> None:
    """Renderiza aba legal (compatibilidade)."""
    renderer = LegalRenderer(svc)
    renderer.render()
