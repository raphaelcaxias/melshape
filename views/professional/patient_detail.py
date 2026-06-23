"""
Melshape — Detalhe do Paciente (visão profissional).

Views Supabase utilizadas:
  vw_evolucao_peso          → histórico de peso
  vw_consumo_diario         → consumo nutricional diário
  vw_score_transformacao    → score global de transformação
  vw_conquistas_usuario     → badges conquistadas
  vw_dashboard_executivo    → resumo completo do paciente
"""
import streamlit as st
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

from views.components.cards import (
    section_header, metric_card, empty_state, divider
)
from views.patient.patient_detail_tabs import _tab_score, _tab_conquistas
from views.professional.patient_actions import render as render_acoes
from views.professional.patient_detail_charts import _tab_peso, _tab_nutricao

logger = logging.getLogger("Melshape.PatientDetail")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limiares de indicadores comportamentais
MOTIVACAO_SUCESSO = 4.0
MOTIVACAO_ALERTA = 3.0
ENERGIA_SUCESSO = 4.0
ENERGIA_ALERTA = 3.0
SONO_SUCESSO = 7.0
SONO_ALERTA = 6.0

# Limites de query
LIMIT_PERFIL = 1
LIMIT_EXECUTIVO = 1

# Fallbacks
DEFAULT_NOME = "—"
DEFAULT_PERFIL = {}


@dataclass
class PatientExecutiveData:
    """Dados executivos do paciente."""
    total_checkins: int = 0
    total_refeicoes: int = 0
    total_badges: int = 0
    xp_total: int = 0
    motivacao_media: float = 0.0
    energia_media: float = 0.0
    qualidade_sono_media: float = 0.0
    maior_peso: Optional[float] = None
    menor_peso: Optional[float] = None


class PatientDetailRenderer:
    """Renderer dedicado para detalhe do paciente."""
    
    def __init__(self, services: Dict[str, Any], professional):
        self.services = services or {}
        self.professional = professional
        self.db = services.get("db")
        self.paciente_nome = self._get_paciente_nome()
        self.perfil: Optional[Dict[str, Any]] = None
        self.perfil_id: Optional[str] = None
    
    def _get_paciente_nome(self) -> str:
        """Obtém nome do paciente do session state com segurança."""
        try:
            return st.session_state.get("pro_selected_patient", "")
        except Exception as e:
            logger.error(f"Erro ao obter nome do paciente: {e}", exc_info=True)
            return ""
    
    def render(self) -> None:
        """Renderiza detalhe do paciente com tratamento de erros."""
        try:
            # Botão voltar
            if st.button("← Voltar ao painel", key="pd_back"):
                st.session_state.page = "pro_dashboard"
                st.rerun()
            
            if not self.paciente_nome:
                empty_state(
                    "👤",
                    "Nenhum paciente selecionado",
                    "Volte à fila e selecione um paciente",
                )
                return
            
            # Busca perfil
            self.perfil = self._get_perfil()
            if not self.perfil:
                st.warning("Paciente não encontrado no banco.")
                return
            
            self.perfil_id = self.perfil.get("id", "")
            
            section_header(
                f"👤 {self.paciente_nome}",
                "Histórico clínico completo",
            )
            
            # Resumo executivo
            self._render_executive_summary()
            
            divider()
            
            # Tabs
            self._render_tabs()
        except Exception as e:
            logger.error(f"Erro ao renderizar detalhe do paciente: {e}", exc_info=True)
            st.error("❌ Erro ao carregar detalhes do paciente.")
    
    def _render_tabs(self) -> None:
        """Renderiza as 6 tabs do paciente com isolamento de falhas."""
        tab_peso, tab_nutri, tab_score, tab_conquistas, tab_acoes, tab_resumo = st.tabs([
            "⚖️ Evolução de Peso",
            "🍽️ Nutrição",
            "🏆 Score",
            "🎖️ Conquistas",
            "📋 Ações Clínicas",
            "📄 Resumo Pré-Consulta",
        ])
        
        with tab_peso:
            self._render_tab_peso()
        
        with tab_nutri:
            self._render_tab_nutri()
        
        with tab_score:
            self._render_tab_score()
        
        with tab_conquistas:
            self._render_tab_conquistas()
        
        with tab_acoes:
            self._render_tab_acoes()
        
        with tab_resumo:
            self._render_tab_resumo()
    
    def _render_tab_peso(self) -> None:
        try:
            _tab_peso(self.db, self.perfil_id, self.paciente_nome)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab peso: {e}", exc_info=True)
            st.error("❌ Erro ao carregar evolução de peso.")
    
    def _render_tab_nutri(self) -> None:
        try:
            _tab_nutricao(self.db, self.perfil_id)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab nutrição: {e}", exc_info=True)
            st.error("❌ Erro ao carregar dados de nutrição.")
    
    def _render_tab_score(self) -> None:
        try:
            _tab_score(self.db, self.perfil_id)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab score: {e}", exc_info=True)
            st.error("❌ Erro ao carregar score.")
    
    def _render_tab_conquistas(self) -> None:
        try:
            _tab_conquistas(self.db, self.perfil_id)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab conquistas: {e}", exc_info=True)
            st.error("❌ Erro ao carregar conquistas.")
    
    def _render_tab_acoes(self) -> None:
        try:
            render_acoes(self.services, self.professional, self.perfil or {})
        except Exception as e:
            logger.error(f"Erro ao renderizar tab ações: {e}", exc_info=True)
            st.error("❌ Erro ao carregar ações clínicas.")
    
    def _render_tab_resumo(self) -> None:
        try:
            from views.professional.consultation_summary_view import render as render_resumo
            render_resumo(self.services, self.professional, self.perfil or {})
        except Exception as e:
            logger.error(f"Erro ao renderizar tab resumo: {e}", exc_info=True)
            st.error("❌ Erro ao carregar resumo pré-consulta.")
    
    @st.cache_data(ttl=60)
    def _get_perfil(_self) -> Optional[Dict[str, Any]]:
        """Busca perfil pelo nome com cache e tratamento de erros."""
        if not _self.paciente_nome:
            return None
        
        # Banco real
        if _self._is_real_db():
            try:
                response = (
                    _self.db.client
                    .table("perfis")
                    .select("id, nome_completo, tipo_jornada, peso_atual")
                    .ilike("nome_completo", f"%{_self.paciente_nome}%")
                    .limit(LIMIT_PERFIL)
                    .execute()
                )
                return response.data[0] if response.data else None
            except Exception as e:
                logger.error(f"Erro ao buscar perfil no Supabase: {e}", exc_info=True)
        
        # Fallback mock
        return _self._get_perfil_mock()
    
    def _get_perfil_mock(self) -> Optional[Dict[str, Any]]:
        """Busca perfil no mock com tratamento de erros."""
        try:
            mock_data = _self.db._mock().get("users", {})
            for user in mock_data.values():
                if _self.paciente_nome.lower() in user.get("name", "").lower():
                    return {
                        "id": user.get("email"),
                        "nome_completo": user.get("name", ""),
                    }
        except Exception as e:
            logger.error(f"Erro ao buscar perfil no mock: {e}", exc_info=True)
        
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
    
    def _render_executive_summary(self) -> None:
        """Renderiza resumo executivo do paciente."""
        exec_data = self._get_executive_data()
        
        self._render_metricas_executivas(exec_data)
        
        # Indicadores comportamentais
        if exec_data.motivacao_media > 0 or exec_data.energia_media > 0:
            self._render_indicadores_comportamentais(exec_data)
    
    def _render_metricas_executivas(self, data: PatientExecutiveData) -> None:
        """Renderiza métricas executivas principais."""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            metric_card(str(data.total_refeicoes), "Refeições registradas", "🍽️")
        with col2:
            metric_card(str(data.total_checkins), "Check-ins totais", "✅")
        with col3:
            metric_card(str(data.total_badges), "Conquistas", "🏅")
        with col4:
            metric_card(str(data.xp_total), "XP Total", "⭐")
    
    def _render_indicadores_comportamentais(self, data: PatientExecutiveData) -> None:
        """Renderiza indicadores comportamentais."""
        st.markdown("##### 🧠 Indicadores Comportamentais")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            cor = self._get_cor_motivacao(data.motivacao_media)
            metric_card(f"{data.motivacao_media:.1f}/5", "Motivação Média", "😊", cor)
        
        with col2:
            cor = self._get_cor_energia(data.energia_media)
            metric_card(f"{data.energia_media:.1f}/5", "Energia Média", "⚡", cor)
        
        with col3:
            cor = self._get_cor_sono(data.qualidade_sono_media)
            metric_card(f"{data.qualidade_sono_media:.1f}h", "Qualidade de Sono", "😴", cor)
    
    def _get_cor_motivacao(self, valor: float) -> str:
        return "success" if valor >= MOTIVACAO_SUCESSO else "warning" if valor >= MOTIVACAO_ALERTA else "error"
    
    def _get_cor_energia(self, valor: float) -> str:
        return "success" if valor >= ENERGIA_SUCESSO else "warning" if valor >= ENERGIA_ALERTA else "error"
    
    def _get_cor_sono(self, valor: float) -> str:
        return "success" if valor >= SONO_SUCESSO else "warning" if valor >= SONO_ALERTA else "error"
    
    @st.cache_data(ttl=60)
    def _get_executive_data(_self) -> PatientExecutiveData:
        """Obtém dados executivos do paciente com cache."""
        if not _self.perfil_id:
            return PatientExecutiveData()
        
        if _self._is_real_db():
            try:
                response = (
                    _self.db.client
                    .table("vw_dashboard_executivo")
                    .select(
                        "total_checkins,total_refeicoes,total_badges,"
                        "xp_total,motivacao_media,energia_media,"
                        "qualidade_sono_media,maior_peso,menor_peso"
                    )
                    .eq("perfil_id", _self.perfil_id)
                    .limit(LIMIT_EXECUTIVO)
                    .execute()
                )
                
                if response.data:
                    row = response.data[0]
                    return _self._parse_executive_row(row)
            except Exception as e:
                logger.error(f"Erro ao buscar dados executivos: {e}", exc_info=True)
        
        return PatientExecutiveData()
    
    def _parse_executive_row(self, row: Dict) -> PatientExecutiveData:
        """Parseia linha executiva com segurança."""
        try:
            return PatientExecutiveData(
                total_checkins=self._parse_int(row.get("total_checkins")),
                total_refeicoes=self._parse_int(row.get("total_refeicoes")),
                total_badges=self._parse_int(row.get("total_badges")),
                xp_total=self._parse_int(row.get("xp_total")),
                motivacao_media=self._parse_float(row.get("motivacao_media")),
                energia_media=self._parse_float(row.get("energia_media")),
                qualidade_sono_media=self._parse_float(row.get("qualidade_sono_media")),
                maior_peso=self._parse_float_optional(row.get("maior_peso")),
                menor_peso=self._parse_float_optional(row.get("menor_peso")),
            )
        except Exception as e:
            logger.error(f"Erro ao parsear dados executivos: {e}", exc_info=True)
            return PatientExecutiveData()
    
    def _parse_int(self, value: Any) -> int:
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _parse_float(self, value: Any) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_float_optional(self, value: Any) -> Optional[float]:
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None


# Função principal de compatibilidade
def render(services: Dict[str, Any], professional) -> None:
    """Função principal de renderização."""
    renderer = PatientDetailRenderer(services, professional)
    renderer.render()
