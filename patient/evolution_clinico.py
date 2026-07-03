"""
Melshape — Evolução: aba clínica (exames + estagnação).
"""
import streamlit as st
from typing import Dict, Any, Optional, List
import logging

from services.evolution_service import EvolutionService
from views.components.cards import empty_state, alert, metric_card

logger = logging.getLogger("Melshape.Clinico")


class ClinicoRenderer:
    """Renderer dedicado para aba clínica."""
    
    # Constantes de limiares clínicos
    GLICEMIA_OTIMA = 100
    GLICEMIA_ATENCAO = 126
    
    # Constantes de estagnação
    ESTAGNACAO_ALERTA = 7
    ESTAGNACAO_CRITICO = 14
    
    # Constantes de formulários
    MAX_INDICADORES_HISTORICO = 5
    
    def __init__(self, svc: EvolutionService, user: Dict[str, Any]):
        self.svc = svc
        self.user = user
        self.health_mode = user.get("health_mode", "general")
    
    def render(self) -> None:
        """Renderiza aba clínica."""
        st.markdown("##### 🧪 Indicadores Clínicos (Exames)")
        
        # Formulário de exames
        self._render_exames_form()
        
        # Histórico de exames
        self._render_exames_historico()
        
        # Estagnação
        self._render_estagnacao()
    
    def _render_exames_form(self) -> None:
        """Renderiza formulário de exames."""
        # Linha 1: Glicemia, Colesterol, HDL
        col1, col2, col3 = st.columns(3)
        
        with col1:
            glicemia = st.number_input(
                "Glicemia (mg/dL)",
                min_value=0.0,
                max_value=500.0,
                value=90.0,
                step=1.0,
                key="ev_glic",
            )
        
        with col2:
            colesterol_total = st.number_input(
                "Colesterol Total",
                min_value=0.0,
                max_value=500.0,
                value=190.0,
                step=1.0,
                key="ev_col",
            )
        
        with col3:
            hdl = st.number_input(
                "HDL (mg/dL)",
                min_value=0.0,
                max_value=200.0,
                value=45.0,
                step=1.0,
                key="ev_hdl",
            )
        
        # Linha 2: Triglicerídeos, Vitamina D, B12
        col4, col5, col6 = st.columns(3)
        
        with col4:
            triglicerideos = st.number_input(
                "Triglicerídeos",
                min_value=0.0,
                max_value=1000.0,
                value=150.0,
                step=1.0,
                key="ev_trig",
            )
        
        with col5:
            vitamina_d = st.number_input(
                "Vitamina D (ng/mL)",
                min_value=0.0,
                max_value=200.0,
                value=30.0,
                step=0.5,
                key="ev_vitd",
            )
        
        with col6:
            b12 = st.number_input(
                "B12 (pg/mL)",
                min_value=0.0,
                max_value=2000.0,
                value=400.0,
                step=10.0,
                key="ev_b12",
            )
        
        # Campos específicos para bariátrica
        ferritina = None
        tsh = None
        
        if self.health_mode == "bariatric":
            col7, col8 = st.columns(2)
            with col7:
                ferritina = st.number_input(
                    "Ferritina (ng/mL)",
                    min_value=0.0,
                    max_value=1000.0,
                    value=50.0,
                    step=1.0,
                    key="ev_ferr",
                )
            with col8:
                tsh = st.number_input(
                    "TSH (mUI/L)",
                    min_value=0.0,
                    max_value=50.0,
                    value=2.5,
                    step=0.1,
                    key="ev_tsh",
                )
        
        if st.button(
            "🧪 Salvar exames",
            type="primary",
            use_container_width=True,
            key="ev_save_exames",
        ):
            self._salvar_exames(
                glicemia, colesterol_total, hdl, triglicerideos,
                vitamina_d, b12, ferritina, tsh
            )
    
    def _salvar_exames(
        self,
        glicemia: float,
        colesterol_total: float,
        hdl: float,
        triglicerideos: float,
        vitamina_d: float,
        b12: float,
        ferritina: Optional[float],
        tsh: Optional[float],
    ) -> None:
        """Salva exames clínicos."""
        dados = self._montar_dados_exames(
            glicemia, colesterol_total, hdl, triglicerideos,
            vitamina_d, b12, ferritina, tsh
        )
        
        if not self._validar_dados_exames(dados):
            return
        
        try:
            success = self.svc.salvar_indicador(dados)
            
            if success:
                st.toast("🧪 Exames salvos!", icon="✅")
                st.cache_data.clear()  # Limpa cache para atualizar dados
                st.rerun()
            else:
                st.error("❌ Erro ao salvar exames.")
        except Exception as e:
            logger.error(f"Erro ao salvar exames: {e}", exc_info=True)
            st.error(f"❌ Erro ao salvar exames: {str(e)}")
    
    def _montar_dados_exames(
        self,
        glicemia: float,
        colesterol_total: float,
        hdl: float,
        triglicerideos: float,
        vitamina_d: float,
        b12: float,
        ferritina: Optional[float],
        tsh: Optional[float],
    ) -> Dict[str, float]:
        """Monta dicionário de dados de exames."""
        dados = {
            "glicemia": glicemia,
            "colesterol_total": colesterol_total,
            "hdl": hdl,
            "triglicerideos": triglicerideos,
            "vitamina_d": vitamina_d,
            "b12": b12,
        }
        
        if ferritina is not None:
            dados["ferritina"] = ferritina
        
        if tsh is not None:
            dados["tsh"] = tsh
        
        return dados
    
    def _validar_dados_exames(self, dados: Dict[str, float]) -> bool:
        """Valida dados de exames antes de salvar."""
        # Validações básicas
        if dados.get("glicemia", 0) < 0:
            st.error("❌ Glicemia não pode ser negativa.")
            return False
        
        if dados.get("colesterol_total", 0) < 0:
            st.error("❌ Colesterol não pode ser negativo.")
            return False
        
        return True
    
    def _render_exames_historico(self) -> None:
        """Renderiza histórico de exames."""
        st.markdown("---")
        
        indicadores = self._get_indicadores()
        
        if not indicadores:
            empty_state(
                "🧪",
                "Nenhum exame registrado",
                "Registre seus exames para acompanhar sua saúde clínica",
            )
            return
        
        self._render_historico_header(len(indicadores))
        
        for indicador in indicadores[:self.MAX_INDICADORES_HISTORICO]:
            self._render_indicador_item(indicador)
    
    @st.cache_data(ttl=60)
    def _get_indicadores(_self) -> List[Dict]:
        """Obtém indicadores clínicos (com cache)."""
        try:
            indicadores = _self.svc.get_indicadores(days=365)
            return indicadores or []
        except Exception as e:
            logger.error(f"Erro ao buscar indicadores: {e}", exc_info=True)
            return []
    
    def _render_historico_header(self, total: int) -> None:
        """Renderiza cabeçalho do histórico."""
        st.markdown(
            f"""
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.6rem;">
                📅 Últimos <b>{min(total, self.MAX_INDICADORES_HISTORICO)}</b> exames registrados
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_indicador_item(self, indicador: Dict[str, Any]) -> None:
        """Renderiza um item do histórico de exames."""
        data = self._formatar_data(indicador.get("data_coleta"))
        glicemia_msg = self._formatar_glicemia(indicador.get("glicemia_jejum"))
        colesterol_msg = self._formatar_colesterol(indicador.get("colesterol_total"))
        
        st.markdown(
            f"""
            <div style="padding: 0.5rem 0;
                border-bottom: 1px solid var(--border-subtle);">
                <div style="font-weight: 600; font-size: 0.88rem; color: var(--text);">
                    {data}
                </div>
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">
                    Glicemia: {glicemia_msg} · Colesterol: {colesterol_msg}
                </div>
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
    
    def _formatar_glicemia(self, glicemia: Any) -> str:
        """Formata glicemia com narrativa contextual."""
        if glicemia is None:
            return "—"
        
        try:
            glic = float(glicemia)
            
            if glic < self.GLICEMIA_OTIMA:
                return f"🟢 {glic:.0f} mg/dL — ótimo"
            elif glic < self.GLICEMIA_ATENCAO:
                return f"🟡 {glic:.0f} mg/dL — atenção"
            else:
                return f"🔴 {glic:.0f} mg/dL — avaliar com profissional"
        except (ValueError, TypeError):
            return "—"
    
    def _formatar_colesterol(self, colesterol: Any) -> str:
        """Formata colesterol de forma segura."""
        if colesterol is None:
            return "—"
        
        try:
            col = float(colesterol)
            return f"{col:.0f} mg/dL"
        except (ValueError, TypeError):
            return "—"
    
    def _render_estagnacao(self) -> None:
        """Renderiza monitoramento de estagnação."""
        st.markdown("---")
        st.markdown("##### ⏸️ Monitoramento de Estagnação")
        
        estagnacao = self._get_estagnacao()
        
        if not estagnacao:
            alert("📈 Dados insuficientes para detectar estagnação.", "info")
            return
        
        dias = self._parse_dias_estagnado(estagnacao)
        
        self._render_alerta_estagnacao(dias)
    
    @st.cache_data(ttl=30)
    def _get_estagnacao(_self) -> Optional[Dict]:
        """Obtém dados de estagnação (com cache)."""
        try:
            return _self.svc.get_estagnacao()
        except Exception as e:
            logger.error(f"Erro ao buscar estagnação: {e}", exc_info=True)
            return None
    
    def _parse_dias_estagnado(self, estagnacao: Dict) -> int:
        """Parse dias estagnado de forma segura."""
        try:
            dias = int(estagnacao.get("dias_estagnado", 0))
            return max(0, dias)
        except (ValueError, TypeError):
            return 0
    
    def _render_alerta_estagnacao(self, dias: int) -> None:
        """Renderiza alerta de estagnação baseado nos dias."""
        if dias >= self.ESTAGNACAO_CRITICO:
            self._render_estagnacao_critica(dias)
        elif dias >= self.ESTAGNACAO_ALERTA:
            self._render_estagnacao_alerta(dias)
        else:
            self._render_estagnacao_normal()
    
    def _render_estagnacao_critica(self, dias: int) -> None:
        """Renderiza alerta de estagnação crítica (>= 14 dias)."""
        alert(
            f"⏸️ Seu peso está estagnado há {dias} dias. "
            f"Isso pode indicar adaptação metabólica — "
            f"considere revisar o plano com seu profissional.",
            "warning",
        )
        
        st.markdown(
            """
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.5rem;">
                💡 <b>Sugestão:</b> aumente a ingestão de proteína ou 
                revise sua rotina de treinos.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_estagnacao_alerta(self, dias: int) -> None:
        """Renderiza alerta de estagnação moderada (>= 7 dias)."""
        alert(
            f"📊 {dias} dias sem variação de peso. "
            f"Normal em alguns momentos da jornada — mantenha a consistência.",
            "info",
        )
    
    def _render_estagnacao_normal(self) -> None:
        """Renderiza alerta de estagnação normal (< 7 dias)."""
        alert("📈 Sem sinais de estagnação. Continue assim!", "success")


# Função de compatibilidade
def _tab_clinico(svc: EvolutionService, user: Dict[str, Any]) -> None:
    """Renderiza aba clínica (compatibilidade)."""
    renderer = ClinicoRenderer(svc, user)
    renderer.render()
