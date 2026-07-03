"""
Melshape — Dashboard Profissional.

Views: vw_dashboard_profissional, vw_fila_atendimento,
       vw_alertas_abertos, vw_pacientes_inativos,
       vw_sem_checkin_recente, vw_pacientes_para_notificar
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from collections import Counter
import logging

from views.components.cards import (
    section_header, metric_card, empty_state, divider
)
from views.professional.dashboard_pro_tabs import (
    _tab_alertas, _tab_inativos, _query, _pro_email,
)
from views.components.notification_inbox import render_pacientes_risco_pro

logger = logging.getLogger("Melshape.DashboardPro")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limiares
ADERENCIA_SUCESSO = 70
CONSISTENCIA_SUCESSO = 70
RISCO_ABANDONO_ALERTA = 50
MAX_ACOES_URGENTES = 3

# Labels de pilares
LABELS_PILAR = {
    "general": "⚖️ Emagrecimento",
    "fitness": "💪 Fitness",
    "bariatric": "🔪 Pós-Bariátrica",
    "glp1": "💉 GLP-1",
}

# Cores do gráfico de pilares
CORES_PILAR = ["#C9A84C", "#6366F1", "#8B5CF6", "#10B981"]

# Prioridades da fila
PRIORIDADE_EMOJI = {
    "URGENTE": "🚨",
    "ALTA": "⚠️",
    "MODERADA": "📋",
    "BAIXA": "✅",
}

PRIORIDADE_COR = {
    "URGENTE": "error",
    "ALTA": "warning",
    "MODERADA": "info",
    "BAIXA": "success",
}

ORDEM_PRIORIDADES = ["URGENTE", "ALTA", "MODERADA", "BAIXA"]

# Fallbacks
DEFAULT_PRO_NAME = "Profissional"
DEFAULT_PILAR = "general"
DEFAULT_PRIORIDADE = "BAIXA"


@dataclass
class DashboardStats:
    """Estatísticas do dashboard profissional."""
    total_pacientes: int = 0
    aderencia_media: float = 0.0
    consistencia_media: float = 0.0
    risco_abandono_medio: float = 0.0
    pacientes_ativos: int = 0


class DashboardProRenderer:
    """Renderer dedicado para dashboard profissional."""
    
    def __init__(self, services: Dict[str, Any], professional):
        self.services = services or {}
        self.professional = professional or {}
        self.db = services.get("db")
        self.pro_name = self._get_pro_name()
    
    def _get_pro_name(self) -> str:
        """Obtém nome do profissional com tratamento de erros."""
        try:
            if hasattr(self.professional, "name"):
                return self.professional.name or DEFAULT_PRO_NAME
            
            if isinstance(self.professional, dict):
                return self.professional.get("name", DEFAULT_PRO_NAME)
            
            return DEFAULT_PRO_NAME
        except Exception as e:
            logger.error(f"Erro ao obter nome do profissional: {e}", exc_info=True)
            return DEFAULT_PRO_NAME
    
    def render(self) -> None:
        """Renderiza dashboard profissional com tratamento de erros."""
        try:
            section_header(
                f"👨‍⚕️ Painel — {self.pro_name}",
                "Visão clínica dos seus pacientes",
            )
            
            # Ações proativas
            self._render_acoes_proativas()
            
            # Tabs
            self._render_tabs()
            
            # Sidebar actions
            self._render_sidebar_actions()
        except Exception as e:
            logger.error(f"Erro ao renderizar dashboard: {e}", exc_info=True)
            st.error("❌ Erro ao carregar dashboard. Tente recarregar a página.")
    
    def _render_tabs(self) -> None:
        """Renderiza as 5 tabs do dashboard."""
        tab_geral, tab_fila, tab_alertas, tab_inativos, tab_risco = st.tabs([
            "📊 Visão Geral",
            "🏥 Fila de Atendimento",
            "🚨 Alertas Clínicos",
            "📵 Inativos",
            "⚠️ Em Risco",
        ])
        
        with tab_geral:
            self._render_tab_geral()
        
        with tab_fila:
            self._render_tab_fila()
        
        with tab_alertas:
            self._render_tab_alertas()
        
        with tab_inativos:
            self._render_tab_inativos()
        
        with tab_risco:
            self._render_tab_risco()
    
    def _render_tab_geral(self) -> None:
        """Renderiza tab de visão geral com tratamento de erros."""
        try:
            self._render_visao_geral()
        except Exception as e:
            logger.error(f"Erro ao renderizar visão geral: {e}", exc_info=True)
            alert("❌ Erro ao carregar visão geral.", "error")
    
    def _render_tab_fila(self) -> None:
        """Renderiza tab de fila com tratamento de erros."""
        try:
            self._render_fila()
        except Exception as e:
            logger.error(f"Erro ao renderizar fila: {e}", exc_info=True)
            alert("❌ Erro ao carregar fila de atendimento.", "error")
    
    def _render_tab_alertas(self) -> None:
        """Renderiza tab de alertas com tratamento de erros."""
        try:
            _tab_alertas(self.db)
        except Exception as e:
            logger.error(f"Erro ao renderizar alertas: {e}", exc_info=True)
            alert("❌ Erro ao carregar alertas clínicos.", "error")
    
    def _render_tab_inativos(self) -> None:
        """Renderiza tab de inativos com tratamento de erros."""
        try:
            _tab_inativos(self.db)
        except Exception as e:
            logger.error(f"Erro ao renderizar inativos: {e}", exc_info=True)
            alert("❌ Erro ao carregar pacientes inativos.", "error")
    
    def _render_tab_risco(self) -> None:
        """Renderiza tab de risco com tratamento de erros."""
        try:
            render_pacientes_risco_pro(self.services)
        except Exception as e:
            logger.error(f"Erro ao renderizar pacientes em risco: {e}", exc_info=True)
            alert("❌ Erro ao carregar pacientes em risco.", "error")
    
    def _render_acoes_proativas(self) -> None:
        """Renderiza ações proativas do RiskService."""
        acoes = self._get_acoes_proativas()
        
        if not acoes:
            return
        
        urgentes = self._filtrar_acoes_urgentes(acoes)
        
        if not urgentes:
            return
        
        for acao in urgentes[:MAX_ACOES_URGENTES]:
            self._render_acao_item(acao)
        
        divider()
    
    def _get_acoes_proativas(self) -> List[Dict]:
        """Obtém ações proativas com tratamento de erros."""
        try:
            from services.risk_service import RiskService
            acoes = RiskService(self.db).acoes_profissional()
            return acoes if isinstance(acoes, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter ações proativas: {e}", exc_info=True)
            return []
    
    def _filtrar_acoes_urgentes(self, acoes: List[Dict]) -> List[Dict]:
        """Filtra ações urgentes."""
        try:
            return [a for a in acoes if a.get("urgencia") == "alta"]
        except Exception as e:
            logger.error(f"Erro ao filtrar ações urgentes: {e}", exc_info=True)
            return []
    
    def _render_acao_item(self, acao: Dict) -> None:
        """Renderiza item de ação proativa."""
        try:
            icone = acao.get("icone", "⚠️")
            paciente = acao.get("paciente", "Paciente")
            motivo = acao.get("motivo", "")
            acao_texto = acao.get("acao", "")
            
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between;
                    align-items: center; padding: 0.65rem 0.95rem;
                    border-left: 4px solid var(--error);
                    background: var(--error-bg);
                    border-radius: 12px; margin-bottom: 0.4rem;">
                    <div>
                        <div style="font-weight: 600; font-size: 0.90rem; color: var(--text);">
                            {icone} {paciente}
                        </div>
                        <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem;">
                            {motivo}
                        </div>
                    </div>
                    <span style="font-size: 0.78rem; font-weight: 700;
                        color: var(--error);">{acao_texto}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar ação item: {e}", exc_info=True)
    
    def _render_visao_geral(self) -> None:
        """Renderiza visão geral."""
        stats = self._get_stats()
        
        self._render_metricas_geral(stats)
        
        divider()
        
        # Distribuição por pilar
        self._render_pilar_distribution()
    
    def _render_metricas_geral(self, stats: DashboardStats) -> None:
        """Renderiza métricas da visão geral."""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            metric_card(str(stats.total_pacientes), "Total de Pacientes", "👥")
        
        with col2:
            cor = self._get_cor_aderencia(stats.aderencia_media)
            metric_card(
                f"{stats.aderencia_media:.0f}%",
                "Aderência Média",
                "📋",
                cor,
            )
        
        with col3:
            cor = self._get_cor_consistencia(stats.consistencia_media)
            metric_card(
                f"{stats.consistencia_media:.0f}%",
                "Consistência Média",
                "🔥",
                cor,
            )
        
        with col4:
            cor = self._get_cor_risco(stats.risco_abandono_medio)
            metric_card(
                f"{stats.risco_abandono_medio:.0f}%",
                "Risco de Abandono",
                "⚠️",
                cor,
            )
    
    def _get_cor_aderencia(self, aderencia: float) -> str:
        """Retorna cor baseada na aderência."""
        return "success" if aderencia >= ADERENCIA_SUCESSO else "warning"
    
    def _get_cor_consistencia(self, consistencia: float) -> str:
        """Retorna cor baseada na consistência."""
        return "success" if consistencia >= CONSISTENCIA_SUCESSO else "warning"
    
    def _get_cor_risco(self, risco: float) -> str:
        """Retorna cor baseada no risco."""
        return "error" if risco >= RISCO_ABANDONO_ALERTA else "warning"
    
    @st.cache_data(ttl=60)
    def _get_stats(_self) -> DashboardStats:
        """Obtém estatísticas do dashboard (com cache)."""
        try:
            dados = _query(
                _self.db,
                "vw_dashboard_profissional",
                "total_pacientes,aderencia_media,consistencia_media,risco_abandono_medio",
            )
            
            if dados and isinstance(dados, list) and len(dados) > 0:
                row = dados[0]
                return DashboardStats(
                    total_pacientes=_self._parse_int(row.get("total_pacientes")),
                    aderencia_media=_self._parse_float(row.get("aderencia_media")),
                    consistencia_media=_self._parse_float(row.get("consistencia_media")),
                    risco_abandono_medio=_self._parse_float(row.get("risco_abandono_medio")),
                )
        except Exception as e:
            logger.error(f"Erro ao obter stats do dashboard: {e}", exc_info=True)
        
        # Fallback
        return _self._get_stats_fallback()
    
    def _get_stats_fallback(self) -> DashboardStats:
        """Obtém stats fallback quando view não está disponível."""
        try:
            pacientes = _query(_self.db, "perfis", "id, tipo_jornada", filtro_pro=True)
            return DashboardStats(total_pacientes=len(pacientes) if pacientes else 0)
        except Exception as e:
            logger.error(f"Erro ao obter stats fallback: {e}", exc_info=True)
            return DashboardStats()
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _parse_float(self, value: Any) -> float:
        """Converte valor para float de forma segura."""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _render_pilar_distribution(self) -> None:
        """Renderiza gráfico de distribuição por pilar."""
        pacientes = self._get_pacientes_por_pilar()
        
        if not pacientes:
            empty_state("📊", "Nenhum paciente cadastrado ainda")
            return
        
        try:
            self._render_grafico_pilares(pacientes)
        except ImportError:
            logger.warning("Plotly não disponível para renderizar gráfico")
            self._render_fallback_pilares(pacientes)
        except Exception as e:
            logger.error(f"Erro ao renderizar gráfico de pilares: {e}", exc_info=True)
            self._render_fallback_pilares(pacientes)
    
    def _get_pacientes_por_pilar(self) -> List[Dict]:
        """Obtém pacientes por pilar."""
        try:
            pacientes = _query(self.db, "perfis", "tipo_jornada", filtro_pro=True)
            return pacientes if isinstance(pacientes, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter pacientes por pilar: {e}", exc_info=True)
            return []
    
    def _render_grafico_pilares(self, pacientes: List[Dict]) -> None:
        """Renderiza gráfico de pilares com Plotly."""
        import plotly.express as px
        import pandas as pd
        
        contagem = Counter(
            p.get("tipo_jornada", DEFAULT_PILAR) for p in pacientes
        )
        
        df_data = pd.DataFrame({
            "Jornada": [LABELS_PILAR.get(k, k) for k in contagem],
            "Total": list(contagem.values()),
        })
        
        fig = px.pie(
            df_data,
            names="Jornada",
            values="Total",
            title="Distribuição por Jornada",
            color_discrete_sequence=CORES_PILAR,
        )
        
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#6B6B6B",
            margin=dict(t=40, b=10, l=10, r=10),
            height=350,
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_fallback_pilares(self, pacientes: List[Dict]) -> None:
        """Renderiza fallback quando Plotly não está disponível."""
        contagem = Counter(
            p.get("tipo_jornada", DEFAULT_PILAR) for p in pacientes
        )
        
        st.markdown(
            """
            <div style="font-size: 0.86rem; color: var(--text-muted); margin-bottom: 0.6rem;">
                📊 <b>Distribuição por Jornada:</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        for pilar, total in contagem.items():
            label = LABELS_PILAR.get(pilar, pilar)
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between;
                    padding: 0.4rem 0; border-bottom: 1px solid var(--border-subtle);">
                    <span>{label}</span>
                    <span style="font-weight: 700;">{total}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def _render_fila(self) -> None:
        """Renderiza fila de atendimento."""
        fila = self._get_fila()
        
        if not fila:
            empty_state(
                "🏥",
                "Fila vazia",
                "Nenhum paciente requer atenção agora",
            )
            return
        
        grupos = self._agrupar_por_prioridade(fila)
        
        for nivel in ORDEM_PRIORIDADES:
            pacientes = grupos.get(nivel, [])
            
            if not pacientes:
                continue
            
            self._render_grupo_prioridade(nivel, pacientes)
    
    def _get_fila(self) -> List[Dict]:
        """Obtém fila de atendimento."""
        try:
            fila = _query(
                self.db,
                "vw_fila_atendimento",
                "nome_completo,score_prioridade,prioridade",
            )
            return fila if isinstance(fila, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter fila: {e}", exc_info=True)
            return []
    
    def _agrupar_por_prioridade(self, fila: List[Dict]) -> Dict[str, List[Dict]]:
        """Agrupa pacientes por prioridade."""
        grupos = {nivel: [] for nivel in ORDEM_PRIORIDADES}
        
        try:
            for p in fila:
                prior = p.get("prioridade", DEFAULT_PRIORIDADE)
                if prior in grupos:
                    grupos[prior].append(p)
                else:
                    grupos[DEFAULT_PRIORIDADE].append(p)
        except Exception as e:
            logger.error(f"Erro ao agrupar por prioridade: {e}", exc_info=True)
        
        return grupos
    
    def _render_grupo_prioridade(self, nivel: str, pacientes: List[Dict]) -> None:
        """Renderiza grupo de pacientes por prioridade."""
        try:
            emoji = PRIORIDADE_EMOJI.get(nivel, "📋")
            cor = PRIORIDADE_COR.get(nivel, "info")
            
            st.markdown(
                f"""
                <div class="alert-{cor}" style="margin-bottom: 0.5rem;">
                    {emoji} <b>{nivel}</b> — {len(pacientes)} paciente(s)
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            for paciente in pacientes:
                self._render_fila_item(paciente)
            
            divider()
        except Exception as e:
            logger.error(f"Erro ao renderizar grupo '{nivel}': {e}", exc_info=True)
    
    def _render_fila_item(self, paciente: Dict) -> None:
        """Renderiza um item da fila."""
        try:
            nome = paciente.get("nome_completo", "—")
            score = self._parse_float(paciente.get("score_prioridade", 0))
            
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                st.markdown(
                    f"""
                    <div style="font-weight: 600; font-size: 0.94rem; color: var(--text);">
                        {nome}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            
            with col2:
                st.markdown(
                    f"""
                    <div style="font-size: 0.82rem; color: var(--text-muted);">
                        Score: {score:.0f}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            
            with col3:
                if st.button(
                    "📄 Resumo",
                    key=f"fila_resumo_{nome}",
                    use_container_width=True,
                    help="Ir direto para o resumo pré-consulta",
                ):
                    self._navegar_para_resumo(nome)

            with col4:
                if st.button(
                    "Ver →",
                    key=f"fila_{nome}",
                    use_container_width=True,
                ):
                    self._navegar_para_paciente(nome)
        except Exception as e:
            logger.error(f"Erro ao renderizar item da fila: {e}", exc_info=True)

    def _navegar_para_resumo(self, nome: str) -> None:
        """Navega direto para a aba de resumo pré-consulta do paciente."""
        try:
            st.session_state["pro_selected_patient"] = nome
            st.session_state["pro_patient_detail_tab"] = "resumo"
            st.session_state.page = "pro_patient_detail"
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para resumo de '{nome}': {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")
    
    def _navegar_para_paciente(self, nome: str) -> None:
        """Navega para detalhes do paciente."""
        try:
            st.session_state["pro_selected_patient"] = nome
            st.session_state.page = "pro_patient_detail"
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para paciente '{nome}': {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")
    
    def _render_sidebar_actions(self) -> None:
        """Renderiza ações na sidebar."""
        try:
            st.sidebar.markdown("---")
            
            if st.sidebar.button("👥 Meus Pacientes", use_container_width=True, key="pro_pacientes_btn"):
                self._navegar_para("pro_pacientes")

            if st.sidebar.button("🔗 Convidar Pacientes", use_container_width=True, key="pro_invite_btn"):
                self._navegar_para("pro_convite")

            if st.sidebar.button("🎯 Triagem", use_container_width=True):
                self._navegar_para("pro_triagem")
            
            if st.sidebar.button(
                "🏥 Dashboard Executivo",
                use_container_width=True,
                key="pro_executive_btn",
            ):
                self._navegar_para("pro_executive")
            
            if st.sidebar.button("🚪 Sair", use_container_width=True):
                self._logout_profissional()
        except Exception as e:
            logger.error(f"Erro ao renderizar sidebar actions: {e}", exc_info=True)
    
    def _navegar_para(self, page: str) -> None:
        """Navega para página."""
        try:
            st.session_state.page = page
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para '{page}': {e}", exc_info=True)
    
    def _logout_profissional(self) -> None:
        """Realiza logout do profissional."""
        try:
            st.session_state.pop("professional", None)
            st.session_state.page = "landing"
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao realizar logout: {e}", exc_info=True)


# Função principal de compatibilidade
def render(services: Dict[str, Any], professional) -> None:
    """Função principal de renderização."""
    renderer = DashboardProRenderer(services, professional)
    renderer.render()
