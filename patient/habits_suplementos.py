"""
Melshape — Hábitos: Aba de Suplementos.
Fundido de supplements.py — suplementos são hábitos clínicos.
Integrado ao Orchestrator via db.add_xp e db.save_supplement.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from datetime import date
import logging

from views.components.cards import empty_state, alert

logger = logging.getLogger("Melshape.Suplementos")


# Constantes
UNIDADES_SUPLEMENTO = ["mg", "g", "ml", "UI", "cápsula", "comprimido"]
XP_REGISTRO_SUPLEMENTO = 10
MAX_SUPLEMENTOS_EXIBIR = 10


class SuplementosRenderer:
    """Renderer dedicado para aba de suplementos."""
    
    def __init__(self, db, user: Dict[str, Any]):
        self.db = db
        self.user = user
        self.health_mode = user.get("health_mode", "general")
    
    def render(self) -> None:
        """Renderiza aba de suplementos."""
        st.markdown("##### 💊 Suplementos de Hoje")
        
        suplementos = self._get_suplementos_hoje()
        
        if suplementos:
            self._render_suplementos(suplementos)
        else:
            empty_state("💊", "Nenhum suplemento registrado hoje")
        
        # Alerta para bariátrico
        self._render_alerta_bariatrico()
        
        st.markdown("---")
        
        # Formulário para registrar
        self._render_form_registro()
    
    @st.cache_data(ttl=30)
    def _get_suplementos_hoje(_self) -> List[Dict]:
        """Obtém suplementos de hoje (com cache)."""
        try:
            suplementos = _self.db.get_supplements_today()
            return suplementos if isinstance(suplementos, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar suplementos de hoje: {e}", exc_info=True)
            return []
    
    def _render_suplementos(self, suplementos: List[Dict]) -> None:
        """Renderiza lista de suplementos do dia."""
        for suplemento in suplementos[:MAX_SUPLEMENTOS_EXIBIR]:
            self._render_suplemento_item(suplemento)
        
        if len(suplementos) > MAX_SUPLEMENTOS_EXIBIR:
            st.info(f"📋 Mostrando {MAX_SUPLEMENTOS_EXIBIR} de {len(suplementos)} suplementos.")
    
    def _render_suplemento_item(self, suplemento: Dict) -> None:
        """Renderiza um item de suplemento."""
        nome = self._extrair_campo(suplemento, "name", "Suplemento")
        dose = self._extrair_campo(suplemento, "dose", "")
        unidade = self._extrair_campo(suplemento, "unit", "")
        
        dose_formatada = f"{dose} {unidade}".strip() if dose else ""
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between;
                align-items: center; padding: 0.6rem 0;
                border-bottom: 1px solid var(--border-subtle);">
                <span style="font-weight: 600; font-size: 0.9rem; color: var(--text);">
                    💊 {nome}
                </span>
                <span style="font-size: 0.84rem; color: var(--text-muted);">
                    {dose_formatada}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _extrair_campo(self, suplemento: Any, campo: str, default: str = "") -> str:
        """Extrai campo de suplemento de forma segura (suporta dict e objeto)."""
        try:
            # Tenta como atributo de objeto
            valor = getattr(suplemento, campo, None)
            
            # Se não encontrou, tenta como dict
            if valor is None and isinstance(suplemento, dict):
                valor = suplemento.get(campo, default)
            
            return str(valor) if valor is not None else default
        except Exception as e:
            logger.debug(f"Erro ao extrair campo '{campo}': {e}")
            return default
    
    def _render_alerta_bariatrico(self) -> None:
        """Renderiza alerta para pacientes bariátricos."""
        if self.health_mode != "bariatric":
            return
        
        try:
            self._render_alerta_bariatrico_interno()
        except Exception as e:
            logger.error(f"Erro ao renderizar alerta bariátrico: {e}", exc_info=True)
    
    def _render_alerta_bariatrico_interno(self) -> None:
        """Lógica interna do alerta bariátrico."""
        from services.bariatric_service import BariatricService
        
        svc = BariatricService(self.db)
        resumo = svc.resumo(self.user)
        
        suplementos_obrigatorios = resumo.get("suplementos", [])
        suplementos_hoje = self._get_suplementos_hoje()
        
        if not suplementos_obrigatorios or suplementos_hoje:
            return
        
        # Monta mensagem com nomes dos suplementos
        nomes = self._formatar_nomes_suplementos(suplementos_obrigatorios)
        fase_nome = resumo.get("fase", {}).get("nome", "—")
        
        alert(
            f"⚕️ Fase {fase_nome} — suplementação obrigatória: {nomes}",
            "warning",
        )
    
    def _formatar_nomes_suplementos(self, suplementos: List[Dict]) -> str:
        """Formata nomes dos suplementos para exibição."""
        try:
            nomes = [s.get("name", "") for s in suplementos[:3]]
            return " · ".join(filter(None, nomes))
        except Exception as e:
            logger.error(f"Erro ao formatar nomes de suplementos: {e}")
            return "suplementos"
    
    def _render_form_registro(self) -> None:
        """Renderiza formulário para registrar suplemento."""
        st.markdown("##### ➕ Registrar Suplemento")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nome = st.text_input(
                "Nome",
                placeholder="Ex: Vitamina D3",
                key="supl_nome",
            )
        
        with col2:
            dose = st.text_input(
                "Dose",
                placeholder="Ex: 2000",
                key="supl_dose",
            )
        
        col3, col4 = st.columns(2)
        
        with col3:
            unidade = st.selectbox(
                "Unidade",
                UNIDADES_SUPLEMENTO,
                key="supl_unit",
            )
        
        with col4:
            observacao = st.text_input(
                "Observação (opcional)",
                key="supl_obs",
            )
        
        if st.button(
            "💊 Registrar suplemento",
            type="primary",
            use_container_width=True,
            key="supl_save",
        ):
            self._registrar_suplemento(nome, dose, unidade, observacao)
    
    def _registrar_suplemento(
        self,
        nome: str,
        dose: str,
        unidade: str,
        observacao: str,
    ) -> None:
        """Registra um suplemento com validações."""
        # Validações
        if not self._validar_campos(nome, dose):
            return
        
        try:
            # Cria objeto Supplement
            suplemento = self._criar_objeto_suplemento(nome, dose, unidade, observacao)
            
            if not suplemento:
                st.error("❌ Erro ao criar objeto de suplemento.")
                return
            
            # Salva no banco
            success = self.db.save_supplement(suplemento)
            
            if success:
                self._processar_sucesso_registro(nome)
            else:
                st.error("❌ Erro ao registrar suplemento.")
        except Exception as e:
            logger.error(f"Erro ao registrar suplemento '{nome}': {e}", exc_info=True)
            st.error(f"❌ Erro ao registrar suplemento: {str(e)}")
    
    def _validar_campos(self, nome: str, dose: str) -> bool:
        """Valida campos obrigatórios."""
        if not nome or not nome.strip():
            st.warning("⚠️ Digite o nome do suplemento.")
            return False
        
        if not dose or not dose.strip():
            st.warning("⚠️ Digite a dose do suplemento.")
            return False
        
        return True
    
    def _criar_objeto_suplemento(
        self,
        nome: str,
        dose: str,
        unidade: str,
        observacao: str,
    ) -> Optional[Any]:
        """Cria objeto Supplement de forma segura."""
        try:
            from core.models import Supplement
            
            return Supplement(
                name=nome.strip(),
                dose=dose.strip(),
                unit=unidade,
                notes=observacao,
                log_date=date.today().isoformat(),
            )
        except Exception as e:
            logger.error(f"Erro ao criar objeto Supplement: {e}", exc_info=True)
            return None
    
    def _processar_sucesso_registro(self, nome: str) -> None:
        """Processa sucesso do registro de suplemento."""
        st.toast("💊 Suplemento registrado!", icon="✅")
        
        # Adiciona XP
        try:
            self.db.add_xp(XP_REGISTRO_SUPLEMENTO, motivo="suplemento")
        except Exception as e:
            logger.error(f"Erro ao adicionar XP: {e}")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()


# Função de compatibilidade
def render_tab_suplementos(db, user: Dict[str, Any]) -> None:
    """Renderiza tab de suplementos (compatibilidade)."""
    renderer = SuplementosRenderer(db, user)
    renderer.render()
