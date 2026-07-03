"""
Melshape — GLP-1: formulários de dose e sintomas.
Importado por glp1.py.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from datetime import date
import json
import logging

from services.glp1_service import GLP1Service
from views.components.cards import alert, xp_toast, show_new_achievements
from config import SEVERE_SYMPTOMS
from config import SYMPTOM_LIST
import config

logger = logging.getLogger("Melshape.GLP1Forms")


class GLP1FormsRenderer:
    """Renderer dedicado para formulários GLP-1."""
    
    # Constantes de XP
    XP_REGISTRO_DOSE = 25
    XP_MONITORAMENTO_SINTOMAS = 10
    
    # Constantes de severidade
    SEVERIDADE_LABELS = {
        1: "1 — Leve",
        2: "2 — Moderada",
        3: "3 — Grave",
    }
    
    def __init__(self, db, svc: GLP1Service, gami, user: Dict[str, Any]):
        self.db = db
        self.svc = svc
        self.gami = gami
        self.user = user
    
    def render_dose(self, resumo: Dict[str, Any]) -> None:
        """Renderiza formulário de dose."""
        st.markdown("##### 💉 Registrar Aplicação")
        
        medicamento_atual = resumo.get("medicamento", "")
        dose_atual = resumo.get("dose_atual", "")
        fase_atual = resumo.get("fase", {}).get("key", "adapting")
        
        # Seleciona medicamento
        medicamentos = self._get_medicamentos()
        med_idx = self._encontrar_indice(medicamento_atual, medicamentos)
        medicamento = st.selectbox(
            "Medicamento",
            medicamentos,
            index=med_idx,
            key="glp1_med",
        )
        
        # Doses disponíveis
        doses_disponiveis = self._get_doses_disponiveis(medicamento)
        dose_idx = self._encontrar_indice(dose_atual, doses_disponiveis)
        dose = st.selectbox(
            "Dose",
            doses_disponiveis,
            index=dose_idx,
            key="glp1_dose_sel",
        )
        
        # Fase
        fases = self._get_fases()
        fase_idx = self._encontrar_indice_chave(fase_atual, fases)
        fase = st.selectbox(
            "Fase atual",
            list(fases.keys()),
            index=fase_idx,
            format_func=lambda k: fases[k],
            key="glp1_fase",
        )
        
        observacao = st.text_input(
            "Observação (opcional)",
            placeholder="Ex: Aplicada no abdômen, sem reações",
            key="glp1_obs",
        )
        
        if st.button(
            "💉 Registrar dose",
            type="primary",
            use_container_width=True,
            key="glp1_save_dose",
        ):
            self._salvar_dose(medicamento, dose, fase, observacao)
    
    def _get_medicamentos(self) -> List[str]:
        """Obtém lista de medicamentos com fallback."""
        try:
            return config.GLP1_MEDICATIONS
        except Exception as e:
            logger.error(f"Erro ao obter medicamentos: {e}")
            return []
    
    def _get_doses_disponiveis(self, medicamento: str) -> List[str]:
        """Obtém doses disponíveis para o medicamento."""
        try:
            doses = config.GLP1_DOSES.get(medicamento, ["Personalizado"])
            return doses if doses else ["Personalizado"]
        except Exception as e:
            logger.error(f"Erro ao obter doses de {medicamento}: {e}")
            return ["Personalizado"]
    
    def _get_fases(self) -> Dict[str, str]:
        """Obtém dicionário de fases com fallback."""
        try:
            return config.GLP1_PHASES
        except Exception as e:
            logger.error(f"Erro ao obter fases: {e}")
            return {"adapting": "Adaptação"}
    
    def _encontrar_indice(self, valor: str, lista: List[str]) -> int:
        """Encontra índice do valor na lista, retorna 0 se não encontrado."""
        try:
            return lista.index(valor) if valor in lista else 0
        except Exception:
            return 0
    
    def _encontrar_indice_chave(self, chave: str, dicionario: Dict) -> int:
        """Encontra índice da chave no dicionário, retorna 0 se não encontrada."""
        try:
            chaves = list(dicionario.keys())
            return chaves.index(chave) if chave in chaves else 0
        except Exception:
            return 0
    
    def _salvar_dose(self, medicamento: str, dose: str, fase: str, obs: str) -> None:
        """Salva dose GLP-1 com tratamento de erros."""
        try:
            # Garante que protocolo existe
            protocolo = self._obter_ou_criar_protocolo(medicamento, dose)
            protocolo_id = protocolo.get("id", "") if protocolo else ""
            
            success = self.db.registrar_dose_glp1(
                medicamento=medicamento,
                dose=dose,
                fase=fase,
                observacao=obs,
                protocolo_id=protocolo_id,
            )
            
            if success:
                self._processar_sucesso_dose(medicamento, dose, fase)
            else:
                st.error("❌ Erro ao registrar dose.")
        except Exception as e:
            logger.error(f"Erro ao salvar dose: {e}", exc_info=True)
            st.error(f"❌ Erro ao registrar dose: {str(e)}")
    
    def _obter_ou_criar_protocolo(self, medicamento: str, dose: str) -> Optional[Dict]:
        """Obtém protocolo ativo ou cria novo."""
        try:
            protocolo = self.db.get_protocolo_ativo()
            if not protocolo:
                protocolo = self.db.criar_protocolo(medicamento, dose)
            return protocolo
        except Exception as e:
            logger.error(f"Erro ao obter/criar protocolo: {e}")
            return None
    
    def _processar_sucesso_dose(self, medicamento: str, dose: str, fase: str) -> None:
        """Processa sucesso do registro de dose."""
        st.toast(f"💉 Dose {dose} registrada!", icon="✅")
        
        # Adiciona XP
        self.db.add_xp(self.XP_REGISTRO_DOSE, "dose_glp1")
        xp_toast(self.XP_REGISTRO_DOSE, "registro de dose")
        
        # Atualiza dados do perfil
        try:
            self.db.update_user({
                "glp1_medication": medicamento,
                "glp1_dose": dose,
                "glp1_phase": fase,
                "uses_glp1": True,
            })
        except Exception as e:
            logger.error(f"Erro ao atualizar perfil: {e}")
        
        # Verifica conquistas
        self._verificar_conquistas()
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def _verificar_conquistas(self) -> None:
        """Verifica e exibe novas conquistas."""
        try:
            novos = self.gami.check_achievements(self.user)
            show_new_achievements(novos)
        except Exception as e:
            logger.error(f"Erro ao verificar conquistas: {e}")
    
    def render_sintomas(self) -> None:
        """Renderiza formulário de sintomas."""
        st.markdown("##### 📋 Registrar Sintomas de Hoje")
        
        # Verifica se já registrou hoje
        if self._ja_registrou_sintomas_hoje():
            alert("✅ Sintomas de hoje já registrados.", "success")
            self._mostrar_sintomas_hoje()
            return
        
        st.markdown(
            """
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.8rem;">
                Marque todos que está sentindo hoje:
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Lista de sintomas
        selecionados = self._render_sintomas_checkboxes()
        
        # Alerta de sintomas graves
        self._render_alertas_graves(selecionados)
        
        # Severidade
        severidade = self._render_severidade_slider()
        
        observacao = st.text_area(
            "Observações (opcional)",
            height=70,
            key="glp1_sint_obs",
            placeholder="Descreva como está se sentindo...",
        )
        
        btn_label = self._get_btn_label_sintomas(selecionados)
        
        if st.button(
            f"📋 {btn_label}",
            type="primary",
            use_container_width=True,
            key="glp1_save_sint",
        ):
            self._salvar_sintomas(selecionados, severidade, observacao)
    
    def _render_severidade_slider(self) -> int:
        """Renderiza slider de severidade."""
        return st.select_slider(
            "Severidade geral",
            options=[1, 2, 3],
            value=1,
            format_func=lambda x: self.SEVERIDADE_LABELS.get(x, "—"),
            key="glp1_sev",
        )
    
    def _get_btn_label_sintomas(self, selecionados: List[str]) -> str:
        """Retorna label do botão baseado nos sintomas selecionados."""
        if not selecionados:
            return "Registrar sem sintomas"
        else:
            return f"Registrar {len(selecionados)} sintoma(s)"
    
    @st.cache_data(ttl=30)
    def _ja_registrou_sintomas_hoje(_self) -> bool:
        """Verifica se já registrou sintomas hoje (com cache)."""
        try:
            hoje = date.today().isoformat()
            sintomas_hoje = _self.db.get_sintomas_glp1(days=1)
            
            if not sintomas_hoje:
                return False
            
            return any(
                s.get("data_registro", "")[:10] == hoje
                for s in sintomas_hoje
            )
        except Exception as e:
            logger.error(f"Erro ao verificar sintomas de hoje: {e}")
            return False
    
    def _render_sintomas_checkboxes(self) -> List[str]:
        """Renderiza checkboxes de sintomas."""
        selecionados = []
        cols = st.columns(2)
        
        for i, (codigo, label) in enumerate(SYMPTOM_LIST):
            with cols[i % 2]:
                if st.checkbox(label, key=f"sint_{codigo}"):
                    selecionados.append(codigo)
        
        return selecionados
    
    def _render_alertas_graves(self, selecionados: List[str]) -> None:
        """Renderiza alertas para sintomas graves."""
        graves = [cod for cod in selecionados if cod in SEVERE_SYMPTOMS]
        
        if not graves:
            return
        
        nomes_graves = self._obter_nomes_sintomas(graves)
        
        alert(
            f"🚨 Sintomas graves identificados: {', '.join(nomes_graves)}. "
            f"Considere contatar seu médico.",
            "error",
        )
    
    def _obter_nomes_sintomas(self, codigos: List[str]) -> List[str]:
        """Obtém nomes dos sintomas a partir dos códigos."""
        try:
            return [
                label for cod, label in SYMPTOM_LIST
                if cod in codigos
            ]
        except Exception as e:
            logger.error(f"Erro ao obter nomes de sintomas: {e}")
            return []
    
    def _salvar_sintomas(self, selecionados: List[str], severidade: int, obs: str) -> None:
        """Salva sintomas GLP-1 com tratamento de erros."""
        try:
            success = self.db.registrar_sintomas_glp1(
                selecionados,
                severidade,
                obs
            )
            
            if success:
                self._processar_sucesso_sintomas()
            else:
                st.error("❌ Erro ao registrar sintomas.")
        except Exception as e:
            logger.error(f"Erro ao salvar sintomas: {e}", exc_info=True)
            st.error(f"❌ Erro ao registrar sintomas: {str(e)}")
    
    def _processar_sucesso_sintomas(self) -> None:
        """Processa sucesso do registro de sintomas."""
        st.toast("📋 Sintomas registrados!", icon="✅")
        
        # Adiciona XP
        self.db.add_xp(self.XP_MONITORAMENTO_SINTOMAS, "monitoramento_glp1")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def _mostrar_sintomas_hoje(self) -> None:
        """Exibe sintomas registrados hoje."""
        sintomas = self._get_sintomas_hoje()
        
        if not sintomas:
            return
        
        s = sintomas[0]
        lista = self._parse_lista_sintomas(s.get("sintomas", []))
        nomes = self._obter_nomes_sintomas(lista)
        severidade = self._parse_severidade(s.get("severidade", 1))
        
        if nomes:
            self._render_sintomas_registrados(nomes, severidade)
        else:
            self._render_sem_sintomas()
    
    @st.cache_data(ttl=30)
    def _get_sintomas_hoje(_self) -> List[Dict]:
        """Obtém sintomas de hoje (com cache)."""
        try:
            return _self.db.get_sintomas_glp1(days=1) or []
        except Exception as e:
            logger.error(f"Erro ao buscar sintomas de hoje: {e}")
            return []
    
    def _parse_lista_sintomas(self, lista_raw: Any) -> List[str]:
        """Parse lista de sintomas de forma segura."""
        if isinstance(lista_raw, list):
            return lista_raw
        
        if isinstance(lista_raw, str):
            try:
                return json.loads(lista_raw)
            except Exception as e:
                logger.warning(f"Erro ao parsear JSON de sintomas: {e}")
                return []
        
        return []
    
    def _parse_severidade(self, severidade_raw: Any) -> int:
        """Parse severidade de forma segura."""
        try:
            severidade = int(severidade_raw)
            return max(1, min(severidade, 3))  # Garante entre 1 e 3
        except (ValueError, TypeError):
            return 1
    
    def _render_sintomas_registrados(self, nomes: List[str], severidade: int) -> None:
        """Renderiza sintomas registrados."""
        st.markdown(
            f"""
            <div style="font-size: 0.86rem; color: var(--text-muted); margin-top: 0.5rem;">
                <b>Sintomas:</b> {", ".join(nomes)} · <b>Severidade:</b> {severidade}/3
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_sem_sintomas(self) -> None:
        """Renderiza mensagem de sem sintomas."""
        st.markdown(
            """
            <div style="font-size: 0.86rem; color: var(--success); margin-top: 0.5rem;">
                ✅ Sem sintomas hoje
            </div>
            """,
            unsafe_allow_html=True,
        )


# Funções de compatibilidade
def render_form_dose(db, svc: GLP1Service, gami, user: Dict[str, Any],
                      resumo: Dict[str, Any]) -> None:
    """Renderiza formulário de dose (compatibilidade)."""
    renderer = GLP1FormsRenderer(db, svc, gami, user)
    renderer.render_dose(resumo)


def render_form_sintomas(db, svc: GLP1Service, gami,
                          user: Dict[str, Any]) -> None:
    """Renderiza formulário de sintomas (compatibilidade)."""
    renderer = GLP1FormsRenderer(db, svc, gami, user)
    renderer.render_sintomas()
