"""
Melshape — Prescrição alimentar do profissional.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from views.components.cards import alert, empty_state, divider

logger = logging.getLogger("Melshape.PatientPrescription")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limites de query
LIMIT_PRESCRICAO_ATIVA = 1
LIMIT_MODELOS = 20

# Fallbacks
DEFAULT_DATA = "—"
DEFAULT_OBJETIVO = "—"
DEFAULT_MODELO_NOME = "—"
SEM_MODELO_LABEL = "— Sem modelo —"

# Chaves de session state
SESSION_KEY_PROFESSIONAL = "professional"


@dataclass
class PrescricaoData:
    """Dados de uma prescrição."""
    objetivo: str = ""
    modelo_id: Optional[str] = None


class PatientPrescriptionRenderer:
    """Renderer dedicado para prescrição alimentar."""
    
    def __init__(self, db):
        self.db = db
    
    def render(self, perfil_id: str, nome: str) -> None:
        """Renderiza tab de prescrição com tratamento de erros."""
        try:
            st.markdown(f"##### 🥗 Prescrição para {nome}")
            
            # Prescrição ativa
            self._render_prescricao_ativa(perfil_id)
            
            divider()
            
            # Nova prescrição
            self._render_nova_prescricao(perfil_id)
        except Exception as e:
            logger.error(f"Erro ao renderizar prescrição: {e}", exc_info=True)
            st.error("❌ Erro ao carregar prescrição.")
    
    def _render_prescricao_ativa(self, perfil_id: str) -> None:
        """Renderiza prescrição ativa com tratamento de erros."""
        try:
            prescricao = self._get_prescricao_ativa(perfil_id)
            
            if prescricao:
                self._render_card_prescricao_ativa(prescricao)
        except Exception as e:
            logger.error(f"Erro ao renderizar prescrição ativa: {e}", exc_info=True)
    
    def _render_card_prescricao_ativa(self, prescricao: Dict) -> None:
        """Renderiza card de prescrição ativa."""
        data_inicio = self._formatar_data(prescricao.get("data_inicio", ""))
        objetivo = prescricao.get("objetivo", DEFAULT_OBJETIVO)
        
        st.markdown(
            f"""
            <div class="alert-success" style="margin: 0.5rem 0;">
                ✅ Prescrição ativa desde <b>{data_inicio}</b><br>
                Objetivo: <b>{objetivo}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _formatar_data(self, data_raw: Any) -> str:
        """Formata data de forma segura."""
        try:
            if not data_raw:
                return DEFAULT_DATA
            return str(data_raw)[:10]
        except Exception as e:
            logger.debug(f"Erro ao formatar data: {e}")
            return DEFAULT_DATA
    
    @st.cache_data(ttl=60)
    def _get_prescricao_ativa(_self, perfil_id: str) -> Optional[Dict]:
        """Busca prescrição ativa do paciente com cache e tratamento de erros."""
        if not _self._is_real_db():
            return None
        
        try:
            response = (
                _self.db.client
                .table("prescricoes")
                .select("data_inicio, objetivo, modelo_id")
                .eq("perfil_id", perfil_id)
                .eq("ativa", True)
                .limit(LIMIT_PRESCRICAO_ATIVA)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar prescrição ativa do perfil {perfil_id}: {e}", exc_info=True)
            return None
    
    def _is_real_db(self) -> bool:
        """Verifica se o banco é real (não mock)."""
        try:
            return (
                hasattr(self.db, "is_real") and
                self.db.is_real and
                hasattr(self.db, "client")
            )
        except Exception as e:
            logger.debug(f"Erro ao verificar banco real: {e}")
            return False
    
    def _render_nova_prescricao(self, perfil_id: str) -> None:
        """Renderiza formulário de nova prescrição."""
        st.markdown("##### 📝 Criar Nova Prescrição")
        
        data = PrescricaoData()
        
        data.objetivo = st.text_input(
            "Objetivo da prescrição",
            placeholder="Ex: Déficit calórico moderado com alta proteína",
            key=f"presc_obj_{perfil_id}",
        )
        
        # Modelos disponíveis
        modelos = self._get_modelos_profissional()
        data.modelo_id = self._render_modelo_selector(modelos)
        
        if st.button(
            "🥗 Criar prescrição",
            type="primary",
            use_container_width=True,
            key=f"presc_save_{perfil_id}",
        ):
            self._criar_prescricao(perfil_id, data)
    
    @st.cache_data(ttl=60)
    def _get_modelos_profissional(_self) -> List[Dict]:
        """Busca modelos do profissional com cache e tratamento de erros."""
        if not _self._is_real_db():
            return []
        
        try:
            pro_id = _self._get_professional_id()
            
            if not pro_id:
                return []
            
            response = (
                _self.db.client
                .table("modelos_refeicao")
                .select("id, nome, descricao")
                .eq("profissional_id", pro_id)
                .limit(LIMIT_MODELOS)
                .execute()
            )
            
            data = response.data or []
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar modelos do profissional: {e}", exc_info=True)
            return []
    
    def _get_professional_id(self) -> Optional[str]:
        """Obtém ID do profissional logado."""
        try:
            pro = st.session_state.get(SESSION_KEY_PROFESSIONAL)
            
            if not pro:
                return None
            
            if hasattr(pro, "id"):
                return pro.id
            
            if isinstance(pro, dict):
                return pro.get("id")
            
            return None
        except Exception as e:
            logger.error(f"Erro ao obter ID do profissional: {e}", exc_info=True)
            return None
    
    def _render_modelo_selector(self, modelos: List[Dict]) -> Optional[str]:
        """Renderiza seletor de modelos com tratamento de erros."""
        try:
            if not modelos:
                self._render_alerta_sem_modelos()
                return None
            
            st.markdown(
                """
                <div style="font-size: 0.82rem; color: var(--text-muted); margin: 0.5rem 0;">
                    Vincular modelo de refeição (opcional):
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            return self._render_selectbox_modelos(modelos)
        except Exception as e:
            logger.error(f"Erro ao renderizar seletor de modelos: {e}", exc_info=True)
            return None
    
    def _render_alerta_sem_modelos(self) -> None:
        """Renderiza alerta quando não há modelos."""
        alert(
            "Crie modelos de refeição no seu perfil profissional "
            "para vinculá-los a prescrições.",
            "info",
        )
    
    def _render_selectbox_modelos(self, modelos: List[Dict]) -> Optional[str]:
        """Renderiza selectbox de modelos."""
        opcoes = self._build_opcoes_modelos(modelos)
        
        idx = st.selectbox(
            "Modelo",
            range(len(opcoes)),
            format_func=lambda i: opcoes[i],
            key="presc_modelo",
            label_visibility="collapsed",
        )
        
        if idx > 0 and idx <= len(modelos):
            return modelos[idx - 1].get("id")
        
        return None
    
    def _build_opcoes_modelos(self, modelos: List[Dict]) -> List[str]:
        """Constrói lista de opções do selectbox."""
        try:
            opcoes = [SEM_MODELO_LABEL]
            
            for m in modelos:
                if isinstance(m, dict):
                    nome = m.get("nome", DEFAULT_MODELO_NOME)
                    opcoes.append(nome)
            
            return opcoes
        except Exception as e:
            logger.error(f"Erro ao construir opções de modelos: {e}", exc_info=True)
            return [SEM_MODELO_LABEL]
    
    def _criar_prescricao(self, perfil_id: str, data: PrescricaoData) -> None:
        """Cria uma nova prescrição com validações."""
        # Validações
        if not self._validar_prescricao(data):
            return
        
        payload = self._build_payload_prescricao(perfil_id, data)
        
        if self._is_real_db():
            self._criar_prescricao_real(payload)
        else:
            self._criar_prescricao_mock()
    
    def _validar_prescricao(self, data: PrescricaoData) -> bool:
        """Valida dados da prescrição."""
        if not data.objetivo or not data.objetivo.strip():
            st.warning("⚠️ Digite o objetivo da prescrição.")
            return False
        
        return True
    
    def _build_payload_prescricao(self, perfil_id: str, data: PrescricaoData) -> Dict:
        """Constrói payload da prescrição."""
        payload = {
            "perfil_id": perfil_id,
            "objetivo": data.objetivo.strip(),
            "ativa": True,
        }
        
        if data.modelo_id:
            payload["modelo_id"] = data.modelo_id
        
        return payload
    
    def _criar_prescricao_real(self, payload: Dict) -> None:
        """Cria prescrição no banco real."""
        try:
            self.db.client.table("prescricoes").insert(payload).execute()
            
            st.toast("🥗 Prescrição criada!", icon="✅")
            
            # Limpa cache e rerun
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao criar prescrição: {e}", exc_info=True)
            st.error(f"❌ Erro ao criar prescrição: {str(e)}")
    
    def _criar_prescricao_mock(self) -> None:
        """Cria prescrição no mock."""
        try:
            st.toast("🥗 Prescrição criada! (mock)", icon="✅")
            
            # Limpa cache e rerun
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao criar prescrição mock: {e}", exc_info=True)
            st.error("❌ Erro ao criar prescrição.")


# Função de compatibilidade
def _tab_prescricao(db, perfil_id: str, nome: str) -> None:
    """Renderiza tab de prescrição (compatibilidade)."""
    try:
        renderer = PatientPrescriptionRenderer(db)
        renderer.render(perfil_id, nome)
    except Exception as e:
        logger.error(f"Erro ao renderizar tab prescrição: {e}", exc_info=True)
        st.error("❌ Erro ao carregar prescrição.")
