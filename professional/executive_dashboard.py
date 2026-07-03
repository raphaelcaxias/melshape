"""
Melshape — Dashboard Executivo.

Para gestores e clínicas. Responde:
- Quantos pacientes estamos retendo?
- Qual pilar tem melhor aderência?
- Quais profissionais têm mais impacto?
- Onde estão os riscos?

Usa: vw_resumo_executivo, vw_prioridade_intervencao,
     vw_campeoes_transformacao, vw_estagnacao_clinica
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from collections import Counter
import logging

from views.components.cards import (
    section_header, metric_card, empty_state, alert, divider
)

logger = logging.getLogger("Melshape.ExecutiveDash")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limiares
PCT_ATIVOS_SUCESSO = 70
ADERENCIA_SUCESSO = 70
ADERENCIA_ALERTA = 50
RISCO_ABANDONO_ERRO = 50
RISCO_ABANDONO_ALERTA = 30
CONSISTENCIA_SAUDAVEL = 70

# Limites de query
LIMIT_STATS = 100
LIMIT_PILARES = 500
LIMIT_CAMPEOES = 10

# Labels de pilares
PILAR_LABELS = {
    "general": "⚖️ Emagrecimento",
    "fitness": "💪 Fitness",
    "bariatric": "🔪 Pós-Bariátrica",
    "glp1": "💉 GLP-1",
}

# Fallbacks
DEFAULT_NOME = "—"
DEFAULT_PROFissional = "Profissional"


@dataclass
class ExecutiveStats:
    """Estatísticas do dashboard executivo."""
    total_pacientes: int = 0
    pacientes_ativos: int = 0
    aderencia_media: float = 0.0
    consistencia_media: float = 0.0
    risco_abandono_medio: float = 0.0
    receita_mensal: float = 0.0


class ExecutiveDashboardRenderer:
    """Renderer dedicado para dashboard executivo."""
    
    def __init__(self, services: Dict[str, Any]):
        self.services = services or {}
        self.db = services.get("db")
    
    def render(self) -> None:
        """Renderiza dashboard executivo com tratamento de erros."""
        try:
            section_header(
                "🏥 Dashboard Executivo",
                "Visão estratégica da clínica",
            )
            
            # Tabs
            self._render_tabs()
        except Exception as e:
            logger.error(f"Erro ao renderizar dashboard executivo: {e}", exc_info=True)
            st.error("❌ Erro ao carregar dashboard executivo. Tente recarregar a página.")
    
    def _render_tabs(self) -> None:
        """Renderiza as 4 tabs do dashboard."""
        tab_visao, tab_retencao, tab_profissionais, tab_campeoes = st.tabs([
            "📊 Visão Geral",
            "🔄 Retenção",
            "👨‍⚕️ Profissionais",
            "🏆 Campeões",
        ])
        
        with tab_visao:
            self._render_tab_visao()
        
        with tab_retencao:
            self._render_tab_retencao()
        
        with tab_profissionais:
            self._render_tab_profissionais()
        
        with tab_campeoes:
            self._render_tab_campeoes()
    
    def _render_tab_visao(self) -> None:
        """Renderiza tab de visão geral com tratamento de erros."""
        try:
            self._render_visao_geral()
        except Exception as e:
            logger.error(f"Erro ao renderizar visão geral: {e}", exc_info=True)
            alert("❌ Erro ao carregar visão geral.", "error")
    
    def _render_tab_retencao(self) -> None:
        """Renderiza tab de retenção com tratamento de erros."""
        try:
            self._render_retencao()
        except Exception as e:
            logger.error(f"Erro ao renderizar retenção: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados de retenção.", "error")
    
    def _render_tab_profissionais(self) -> None:
        """Renderiza tab de profissionais com tratamento de erros."""
        try:
            self._render_profissionais()
        except Exception as e:
            logger.error(f"Erro ao renderizar profissionais: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados de profissionais.", "error")
    
    def _render_tab_campeoes(self) -> None:
        """Renderiza tab de campeões com tratamento de erros."""
        try:
            self._render_campeoes()
        except Exception as e:
            logger.error(f"Erro ao renderizar campeões: {e}", exc_info=True)
            alert("❌ Erro ao carregar campeões.", "error")
    
    def _render_visao_geral(self) -> None:
        """Renderiza visão geral com comparativo mensal (Sprint 4)."""
        stats = self._get_stats()
        stats_anterior = self._get_stats_mes_anterior()

        self._render_metricas_geral(stats, stats_anterior)

        # Receita estimada
        if stats.receita_mensal > 0:
            divider()
            self._render_card_receita(stats.receita_mensal)

        divider()

        # Distribuição por pilar
        self._render_pilar_distribution()

        divider()

        # Consistência média
        self._render_consistencia_card(stats.consistencia_media)

        divider()

        # Exportação de dados (LGPD)
        self._render_exportacao()

    def _get_stats_mes_anterior(self) -> "ExecutiveStats":
        """Busca stats do mês anterior para comparativo."""
        try:
            from datetime import date
            hoje = date.today()
            primeiro_mes = hoje.replace(day=1)
            from datetime import timedelta
            ultimo_mes_anterior = primeiro_mes - timedelta(days=1)
            primeiro_mes_anterior = ultimo_mes_anterior.replace(day=1)

            if self._is_real_db():
                r = (
                    self.db.client
                    .table("vw_retencao_mensal")
                    .select("total_pacientes,pacientes_ativos,aderencia_media")
                    .eq("mes", primeiro_mes_anterior.strftime("%Y-%m"))
                    .limit(1)
                    .execute()
                )
                if r.data:
                    row = r.data[0]
                    return ExecutiveStats(
                        total_pacientes=self._parse_int(row.get("total_pacientes")),
                        pacientes_ativos=self._parse_int(row.get("pacientes_ativos")),
                        aderencia_media=self._parse_float(row.get("aderencia_media")),
                    )
        except Exception as e:
            logger.debug(f"_get_stats_mes_anterior: {e}")
        return ExecutiveStats()

    def _render_exportacao(self) -> None:
        """Exportação de dados em CSV (obrigação LGPD — Auditoria Mestra)."""
        st.markdown(
            """
            <div style="font-size:0.74rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.08em;color:var(--text-faint);margin-bottom:0.6rem;">
                📥 Exportar Dados
            </div>
            """,
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Exportar Pacientes (CSV)",
                         use_container_width=True, key="exec_export_pac"):
                csv = self._gerar_csv_pacientes()
                if csv:
                    from datetime import date
                    st.download_button(
                        "⬇️ Baixar CSV",
                        data=csv,
                        file_name=f"melshape_pacientes_{date.today()}.csv",
                        mime="text/csv",
                        key="exec_dl_pac",
                    )
        with col2:
            if st.button("📋 Exportar Aderência (CSV)",
                         use_container_width=True, key="exec_export_ader"):
                csv = self._gerar_csv_aderencia()
                if csv:
                    from datetime import date
                    st.download_button(
                        "⬇️ Baixar CSV",
                        data=csv,
                        file_name=f"melshape_aderencia_{date.today()}.csv",
                        mime="text/csv",
                        key="exec_dl_ader",
                    )
        st.caption("🔒 Exportações em conformidade com a LGPD. "
                   "Dados anonimizados disponíveis mediante solicitação.")

    def _gerar_csv_pacientes(self) -> str | None:
        """Gera CSV de pacientes da clínica."""
        try:
            pacientes = self._query(
                "perfis",
                "nome_completo,tipo_jornada,created_at",
                limit=500,
            )
            if not pacientes:
                st.warning("Nenhum dado encontrado para exportar.")
                return None
            import io, csv
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=["nome_completo", "tipo_jornada", "created_at"])
            writer.writeheader()
            for p in pacientes:
                writer.writerow({
                    "nome_completo": p.get("nome_completo", ""),
                    "tipo_jornada": p.get("tipo_jornada", ""),
                    "created_at": str(p.get("created_at", ""))[:10],
                })
            return buf.getvalue()
        except Exception as e:
            logger.error(f"_gerar_csv_pacientes: {e}")
            st.error("Erro ao gerar exportação.")
            return None

    def _gerar_csv_aderencia(self) -> str | None:
        """Gera CSV de aderência por mês."""
        try:
            dados = self._query(
                "vw_retencao_mensal",
                "mes,total_pacientes,pacientes_ativos,aderencia_media",
                limit=24,
                filtro_clinic=True,
            )
            if not dados:
                st.warning("Nenhum dado de retenção encontrado.")
                return None
            import io, csv
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=["mes", "total_pacientes", "pacientes_ativos", "aderencia_media"])
            writer.writeheader()
            for d in dados:
                writer.writerow(d)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"_gerar_csv_aderencia: {e}")
            st.error("Erro ao gerar exportação.")
            return None

    
    def _render_metricas_geral(self, stats: ExecutiveStats, anterior: "ExecutiveStats | None" = None) -> None:
        """Renderiza métricas com variação vs mês anterior (Sprint 4)."""
        col1, col2, col3, col4 = st.columns(4)

        def _delta(atual: float, prev: float) -> str:
            if prev == 0:
                return ""
            diff = atual - prev
            sinal = "+" if diff >= 0 else ""
            return f"{sinal}{diff:.0f}"

        with col1:
            metric_card(str(stats.total_pacientes), "Total de Pacientes", "👥")

        with col2:
            pct_ativos = self._calcular_pct_ativos(stats)
            cor = self._get_cor_ativos(pct_ativos)
            delta = ""
            if anterior and anterior.pacientes_ativos:
                d = stats.pacientes_ativos - anterior.pacientes_ativos
                delta = f" ({'+' if d >= 0 else ''}{d} vs mês anterior)"
            metric_card(
                f"{stats.pacientes_ativos} ({pct_ativos}%){delta}",
                "Pacientes Ativos (7d)",
                "✅",
                cor,
            )

        with col3:
            cor = self._get_cor_aderencia(stats.aderencia_media)
            delta = ""
            if anterior and anterior.aderencia_media:
                d = stats.aderencia_media - anterior.aderencia_media
                delta = f" ({'+' if d >= 0 else ''}{d:.0f}pp)"
            metric_card(
                f"{stats.aderencia_media:.0f}%{delta}",
                "Aderência Média",
                "📋",
                cor,
            )

        with col4:
            cor = self._get_cor_risco(stats.risco_abandono_medio)
            metric_card(f"{stats.risco_abandono_medio:.0f}%", "Risco de Abandono", "⚠️", cor)
    
    def _calcular_pct_ativos(self, stats: ExecutiveStats) -> int:
        """Calcula percentual de ativos com proteção contra divisão por zero."""
        try:
            if stats.total_pacientes <= 0:
                return 0
            return round(stats.pacientes_ativos / stats.total_pacientes * 100)
        except Exception as e:
            logger.debug(f"Erro ao calcular pct ativos: {e}")
            return 0
    
    def _get_cor_ativos(self, pct: int) -> str:
        """Retorna cor baseada no percentual de ativos."""
        return "success" if pct >= PCT_ATIVOS_SUCESSO else "warning"
    
    def _get_cor_aderencia(self, aderencia: float) -> str:
        """Retorna cor baseada na aderência."""
        if aderencia >= ADERENCIA_SUCESSO:
            return "success"
        elif aderencia >= ADERENCIA_ALERTA:
            return "warning"
        return "error"
    
    def _get_cor_risco(self, risco: float) -> str:
        """Retorna cor baseada no risco."""
        if risco >= RISCO_ABANDONO_ERRO:
            return "error"
        elif risco >= RISCO_ABANDONO_ALERTA:
            return "warning"
        return "success"
    
    def _render_card_receita(self, receita: float) -> None:
        """Renderiza card de receita."""
        try:
            st.markdown(
                f"""
                <div class="metric-card fade-in" style="text-align: center;">
                    <div style="font-size: 0.76rem; color: var(--text-muted);
                        text-transform: uppercase; letter-spacing: 0.08em;">
                        Receita Estimada/Mês
                    </div>
                    <div style="font-size: 2.1rem; font-weight: 800; color: var(--primary);
                        margin-top: 0.3rem;">
                        R$ {receita:,.2f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar card receita: {e}", exc_info=True)
    
    @st.cache_data(ttl=60)
    def _get_stats(_self) -> ExecutiveStats:
        """Obtém estatísticas do dashboard executivo (com cache)."""
        try:
            resumo = _self._query(
                "vw_resumo_executivo",
                "total_pacientes,aderencia_media,consistencia_media,"
                "risco_abandono_medio,receita_mensal,pacientes_ativos",
            )
            
            if resumo and isinstance(resumo, list) and len(resumo) > 0:
                row = resumo[0]
                return ExecutiveStats(
                    total_pacientes=_self._parse_int(row.get("total_pacientes")),
                    pacientes_ativos=_self._parse_int(row.get("pacientes_ativos")),
                    aderencia_media=_self._parse_float(row.get("aderencia_media")),
                    consistencia_media=_self._parse_float(row.get("consistencia_media")),
                    risco_abandono_medio=_self._parse_float(row.get("risco_abandono_medio")),
                    receita_mensal=_self._parse_float(row.get("receita_mensal")),
                )
        except Exception as e:
            logger.error(f"Erro ao obter stats executivo: {e}", exc_info=True)
        
        # Fallback
        return _self._get_stats_fallback()
    
    def _get_stats_fallback(self) -> ExecutiveStats:
        """Obtém stats fallback quando view não está disponível."""
        try:
            pacientes = _self._query("perfis", "id, tipo_jornada", limit=200)
            return ExecutiveStats(total_pacientes=len(pacientes) if pacientes else 0)
        except Exception as e:
            logger.error(f"Erro ao obter stats fallback: {e}", exc_info=True)
            return ExecutiveStats()
    
    def _render_pilar_distribution(self) -> None:
        """Renderiza distribuição por pilar."""
        st.markdown("##### 🗺️ Distribuição por Pilar")
        
        pacientes = self._get_pacientes_por_pilar()
        
        if not pacientes:
            empty_state("📊", "Nenhum paciente cadastrado ainda")
            return
        
        pilares = self._contar_pilares(pacientes)
        self._render_pilar_bars(pilares)
    
    def _get_pacientes_por_pilar(self) -> List[Dict]:
        """Obtém pacientes por pilar."""
        try:
            return self._query("perfis", "tipo_jornada", limit=LIMIT_PILARES)
        except Exception as e:
            logger.error(f"Erro ao obter pacientes por pilar: {e}", exc_info=True)
            return []
    
    def _contar_pilares(self, pacientes: List[Dict]) -> Dict[str, int]:
        """Conta pacientes por pilar."""
        try:
            return Counter(p.get("tipo_jornada", "general") for p in pacientes)
        except Exception as e:
            logger.error(f"Erro ao contar pilares: {e}", exc_info=True)
            return {}
    
    def _render_pilar_bars(self, pilares: Dict[str, int]) -> None:
        """Renderiza barras de distribuição por pilar."""
        try:
            total = sum(pilares.values()) or 1
            
            for key, label in PILAR_LABELS.items():
                count = pilares.get(key, 0)
                pct = round(count / total * 100)
                
                self._render_pilar_bar_item(label, count, pct)
        except Exception as e:
            logger.error(f"Erro ao renderizar barras de pilares: {e}", exc_info=True)
    
    def _render_pilar_bar_item(self, label: str, count: int, pct: int) -> None:
        """Renderiza item de barra de pilar."""
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 0.9rem;
                margin-bottom: 0.6rem;">
                <div style="width: 130px; font-size: 0.84rem; color: var(--text);">
                    {label}
                </div>
                <div class="progress-track" style="flex: 1;">
                    <div class="progress-fill" style="width: {pct}%;"></div>
                </div>
                <div style="width: 60px; text-align: right; font-weight: 700;
                    font-size: 0.84rem; color: var(--text);">
                    {count} ({pct}%)
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_consistencia_card(self, consistencia: float) -> None:
        """Renderiza card de consistência."""
        try:
            st.markdown("##### 🔥 Consistência da Clínica")
            
            consistencia_pct = min(100, max(0, consistencia))
            mensagem = self._get_mensagem_consistencia(consistencia_pct)
            
            st.markdown(
                f"""
                <div class="metric-card fade-in">
                    <div style="display: flex; justify-content: space-between;
                        align-items: center; margin-bottom: 0.6rem;">
                        <span style="font-weight: 600; font-size: 0.92rem;">
                            Consistência Média da Clínica
                        </span>
                        <span style="font-weight: 800; font-size: 1.25rem; color: var(--primary);">
                            {consistencia_pct:.0f}%
                        </span>
                    </div>
                    <div class="progress-track">
                        <div class="progress-fill" style="width: {consistencia_pct}%;"></div>
                    </div>
                    <div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.45rem;">
                        {mensagem}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar card consistência: {e}", exc_info=True)
    
    def _get_mensagem_consistencia(self, consistencia: float) -> str:
        """Retorna mensagem baseada na consistência."""
        if consistencia >= CONSISTENCIA_SAUDAVEL:
            return "✅ Consistência saudável"
        return "⚠️ Abaixo do esperado — revisar estratégias"
    
    def _render_retencao(self) -> None:
        """Renderiza tab de retenção."""
        st.markdown("##### 🔄 Retenção de Pacientes")
        
        retencao = self._get_retencao()
        
        if not retencao:
            empty_state("🔄", "Dados de retenção em construção")
            return
        
        self._render_retencao_chart(retencao)
    
    @st.cache_data(ttl=60)
    def _get_retencao(_self) -> List[Dict]:
        """Obtém dados de retenção (com cache)."""
        try:
            return _self._query(
                "vw_retencao_mensal",
                "mes, total_pacientes, pacientes_ativos, taxa_retencao",
            )
        except Exception as e:
            logger.error(f"Erro ao obter retenção: {e}", exc_info=True)
            return []
    
    def _render_retencao_chart(self, dados: List[Dict]) -> None:
        """Renderiza gráfico de retenção com proteção contra ImportError."""
        try:
            import plotly.express as px
            import pandas as pd
            
            df = pd.DataFrame({
                "Mês": [d.get("mes", "") for d in dados],
                "Taxa de Retenção": [self._parse_float(d.get("taxa_retencao")) for d in dados],
            })
            
            fig = px.line(
                df,
                x="Mês",
                y="Taxa de Retenção",
                title="Taxa de Retenção Mensal",
                markers=True,
                color_discrete_sequence=["#C9A84C"],
            )
            
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#6B6B6B",
                margin=dict(t=40, b=30, l=30, r=10),
                height=300,
            )
            
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            logger.warning("Plotly não disponível para renderizar gráfico de retenção")
            self._render_retencao_fallback(dados)
        except Exception as e:
            logger.error(f"Erro ao renderizar gráfico de retenção: {e}", exc_info=True)
            self._render_retencao_fallback(dados)
    
    def _render_retencao_fallback(self, dados: List[Dict]) -> None:
        """Renderiza fallback quando Plotly não está disponível."""
        st.markdown(
            """
            <div style="font-size: 0.86rem; color: var(--text-muted); margin-bottom: 0.6rem;">
                📊 <b>Taxa de Retenção Mensal:</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        for d in dados:
            mes = d.get("mes", "—")
            taxa = self._parse_float(d.get("taxa_retencao"))
            
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between;
                    padding: 0.4rem 0; border-bottom: 1px solid var(--border-subtle);">
                    <span>{mes}</span>
                    <span style="font-weight: 700;">{taxa:.0f}%</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def _render_profissionais(self) -> None:
        """Renderiza tab de profissionais."""
        st.markdown("##### 👨‍⚕️ Performance dos Profissionais")
        
        profissionais = self._get_profissionais()
        
        if not profissionais:
            empty_state("👨‍⚕️", "Sem dados de profissionais")
            return
        
        for pro in profissionais:
            self._render_profissional_item(pro)
    
    @st.cache_data(ttl=60)
    def _get_profissionais(_self) -> List[Dict]:
        """Obtém dados de profissionais (com cache)."""
        try:
            return _self._query(
                "vw_performance_profissionais",
                "nome, total_pacientes, aderencia_media, taxa_retencao",
            )
        except Exception as e:
            logger.error(f"Erro ao obter profissionais: {e}", exc_info=True)
            return []
    
    def _render_profissional_item(self, pro: Dict) -> None:
        """Renderiza item de profissional com tratamento de erros."""
        try:
            if not isinstance(pro, dict):
                return
            
            nome = pro.get("nome", DEFAULT_PROFissional)
            total_pacientes = self._parse_int(pro.get("total_pacientes", 0))
            aderencia = self._parse_float(pro.get("aderencia_media", 0))
            retencao = self._parse_float(pro.get("taxa_retencao", 0))
            
            st.markdown(
                f"""
                <div class="metric-card fade-in" style="margin-bottom: 0.6rem;">
                    <div style="display: flex; justify-content: space-between;
                        align-items: center;">
                        <div>
                            <div style="font-weight: 700; color: var(--text); font-size: 0.94rem;">
                                {nome}
                            </div>
                            <div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.2rem;">
                                {total_pacientes} pacientes
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-weight: 700; color: var(--primary); font-size: 0.92rem;">
                                {aderencia:.0f}% aderência
                            </div>
                            <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 0.15rem;">
                                Retenção: {retencao:.0f}%
                            </div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar profissional item: {e}", exc_info=True)
    
    def _render_campeoes(self) -> None:
        """Renderiza tab de campeões."""
        st.markdown("##### 🏆 Campeões de Transformação")
        
        campeoes = self._get_campeoes()
        
        if not campeoes:
            empty_state(
                "🏆",
                "Sem campeões ainda",
                "Os dados aparecerão conforme os pacientes evoluem",
            )
            return
        
        for i, campeao in enumerate(campeoes[:LIMIT_CAMPEOES]):
            self._render_campeao_item(i, campeao)
    
    @st.cache_data(ttl=60)
    def _get_campeoes(_self) -> List[Dict]:
        """Obtém campeões (com cache)."""
        try:
            return _self._query(
                "vw_campeoes_transformacao",
                "nome_completo, score_transformacao, total_badges, xp_total",
            )
        except Exception as e:
            logger.error(f"Erro ao obter campeões: {e}", exc_info=True)
            return []
    
    def _render_campeao_item(self, posicao: int, campeao: Dict) -> None:
        """Renderiza item de campeão com tratamento de erros."""
        try:
            if not isinstance(campeao, dict):
                return
            
            medalha = self._get_medalha(posicao)
            nome = campeao.get("nome_completo", DEFAULT_NOME)
            score = self._parse_float(campeao.get("score_transformacao", 0))
            badges = self._parse_int(campeao.get("total_badges", 0))
            xp = self._parse_int(campeao.get("xp_total", 0))
            
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between;
                    align-items: center; padding: 0.6rem 0.9rem;
                    border-bottom: 1px solid var(--border-subtle);">
                    <div style="display: flex; align-items: center; gap: 0.9rem;">
                        <span style="font-size: 1.3rem; font-weight: 700;
                            color: var(--primary);">{medalha}</span>
                        <div>
                            <div style="font-weight: 600; color: var(--text); font-size: 0.92rem;">
                                {nome}
                            </div>
                            <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 0.15rem;">
                                {badges} badges
                            </div>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 800; color: var(--primary); font-size: 0.95rem;">
                            {score:.0f}
                        </div>
                        <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 0.15rem;">
                            {xp} XP
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar campeão item: {e}", exc_info=True)
    
    def _get_medalha(self, posicao: int) -> str:
        """Retorna medalha baseada na posição."""
        if posicao == 0:
            return "🥇"
        elif posicao == 1:
            return "🥈"
        elif posicao == 2:
            return "🥉"
        return f"#{posicao + 1}"
    
    @st.cache_data(ttl=60)
    def _get_clinic_id(self) -> str:
        """
        Retorna o effective_clinic_id do profissional logado.
        Sprint 4 — Multitenancy: cada profissional vê apenas dados da própria clínica.
        """
        try:
            pro = st.session_state.get("professional", {})
            if hasattr(pro, "effective_clinic_id"):
                return pro.effective_clinic_id
            if isinstance(pro, dict):
                return pro.get("clinic_id") or pro.get("email", "")
            return ""
        except Exception:
            return ""

    def _query(
        _self,
        tabela: str,
        colunas: str,
        limit: int = LIMIT_STATS,
        filtro_clinic: bool = True,
    ) -> List[Dict]:
        """
        Query Supabase com isolamento por clinic_id (Sprint 4 — Multitenancy).
        filtro_clinic=False apenas para views que já têm filtro embutido.
        """
        if not _self._is_real_db():
            return []

        try:
            query = (
                _self.db.client
                .table(tabela)
                .select(colunas)
                .limit(limit)
            )

            if filtro_clinic:
                clinic_id = _self._get_clinic_id()
                if clinic_id:
                    tabelas_clinic = {
                        "perfis", "vw_resumo_executivo", "vw_retencao_mensal",
                        "vw_campeoes_transformacao", "vw_performance_profissionais",
                    }
                    tabelas_pro = {
                        "vw_alertas_abertos", "vw_fila_atendimento",
                        "vw_estagnacao_clinica", "vw_prioridade_intervencao",
                    }
                    if tabela in tabelas_clinic:
                        try:
                            query = query.eq("clinic_id", clinic_id)
                        except Exception:
                            pass
                    elif tabela in tabelas_pro:
                        try:
                            query = query.eq("profissional_id", clinic_id)
                        except Exception:
                            pass

            result = query.execute()
            data = result.data or []
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Erro ao executar query em '{tabela}': {e}", exc_info=True)
            return []
    
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


# Função principal de compatibilidade
def render(services: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = ExecutiveDashboardRenderer(services)
    renderer.render()
