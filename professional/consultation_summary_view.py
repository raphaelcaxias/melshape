"""
Melshape — Tela de Resumo Pré-Consulta.

O profissional chega na consulta sabendo exatamente:
- Como o paciente evoluiu (peso, hábitos, nutrição)
- Como ele estava emocionalmente (check-ins)
- O que foi combinado na última consulta (condutas)
- O que precisa de atenção (alertas)

Elimina 30 min de trabalho por consulta.
Justifica pagamento mensal do profissional.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from services.consultation_summary import ConsultationSummaryService
from views.components.cards import (
    section_header, empty_state, metric_card, alert, divider
)

logger = logging.getLogger("Melshape.ConsultationSummary")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Períodos disponíveis
PERIODOS_DISPONIVEIS = [7, 14, 30, 60, 90]
PERIODO_PADRAO_IDX = 2  # 30 dias

# Limiares
ADERENCIA_SUCESSO = 70
ADERENCIA_ALERTA = 50
PCT_CHECKIN_SUCESSO = 70
PCT_CHECKIN_ALERTA = 40
GRAVIDADE_ERRO = 3
GRAVIDADE_WARNING = 2

# Limites de exibição
MAX_METAS_EXIBIR = 3
MAX_CONDUTAS_EXIBIR = 3

# Chaves de session state
SESSION_KEY_RESUMO = "cs_resumo"
SESSION_KEY_PERIODO = "cs_periodo"

# Fallbacks
DEFAULT_NOME = "Paciente"
DEFAULT_METRIC_VALUE = "—"


@dataclass
class SummaryMetrics:
    """Métricas do resumo pré-consulta."""
    variacao_peso: Optional[float] = None
    aderencia: float = 0.0
    total_checkins: int = 0
    pct_checkins: int = 0
    total_refeicoes: int = 0
    pct_dias_registro: int = 0
    streak: int = 0
    xp: int = 0
    badges: int = 0


class ConsultationSummaryRenderer:
    """Renderer dedicado para resumo pré-consulta."""
    
    def __init__(self, services: Dict[str, Any], professional, paciente: Dict[str, Any]):
        self.services = services or {}
        self.professional = professional
        self.paciente = paciente or {}
        self.db = services.get("db")
        self.perfil_id = self._get_perfil_id()
        self.nome = self._get_nome_paciente()
        self.svc = self._init_summary_service()
    
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
    
    def _init_summary_service(self) -> Optional[ConsultationSummaryService]:
        """Inicializa ConsultationSummaryService com tratamento de erros."""
        if not self.db:
            logger.error("Database não disponível para ConsultationSummaryRenderer")
            return None
        
        try:
            return ConsultationSummaryService(self.db)
        except Exception as e:
            logger.error(f"Erro ao inicializar ConsultationSummaryService: {e}", exc_info=True)
            return None
    
    def render(self) -> None:
        """Renderiza tela de resumo pré-consulta."""
        try:
            section_header(
                f"📋 Resumo Pré-Consulta — {self.nome}",
                "Últimos 30 dias em um olhar",
            )
            
            # Verifica se serviço foi inicializado
            if not self.svc:
                alert("❌ Não foi possível carregar o serviço de resumo.", "error")
                return
            
            # Seletor de período
            dias = self._render_period_selector()
            
            # Gera/obtém resumo
            resumo = self._get_or_generate_summary(dias)
            
            if not resumo:
                empty_state(
                    "📋",
                    "Nenhum dado disponível",
                    "O paciente precisa ter registros no período selecionado",
                )
                return
            
            # Renderiza conteúdo
            self._render_resumo(resumo)
        except Exception as e:
            logger.error(f"Erro ao renderizar resumo: {e}", exc_info=True)
            alert("❌ Erro ao carregar resumo. Tente recarregar a página.", "error")
    
    def _render_period_selector(self) -> int:
        """Renderiza seletor de período."""
        col_per, col_btn = st.columns([2, 1])
        
        with col_per:
            dias = st.selectbox(
                "Período",
                PERIODOS_DISPONIVEIS,
                index=PERIODO_PADRAO_IDX,
                format_func=lambda x: f"Últimos {x} dias",
                key=SESSION_KEY_PERIODO,
                label_visibility="collapsed",
            )
        
        with col_btn:
            gerar = st.button(
                "🔄 Gerar resumo",
                type="primary",
                use_container_width=True,
                key="cs_gerar",
            )
        
        # Gera resumo se necessário
        if SESSION_KEY_RESUMO not in st.session_state or gerar:
            self._gerar_resumo(dias)
        
        return dias
    
    def _gerar_resumo(self, dias: int) -> None:
        """Gera resumo e armazena no session state."""
        try:
            with st.spinner("Gerando resumo..."):
                resumo = self.svc.gerar(self.perfil_id, dias=dias)
                st.session_state[SESSION_KEY_RESUMO] = resumo
        except Exception as e:
            logger.error(f"Erro ao gerar resumo: {e}", exc_info=True)
            st.session_state[SESSION_KEY_RESUMO] = None
            alert("❌ Erro ao gerar resumo. Tente novamente.", "error")
    
    def _get_or_generate_summary(self, dias: int) -> Optional[Dict]:
        """Obtém ou gera resumo."""
        try:
            if SESSION_KEY_RESUMO in st.session_state:
                resumo = st.session_state.get(SESSION_KEY_RESUMO)
                return resumo if isinstance(resumo, dict) else None
            
            return self.svc.gerar(self.perfil_id, dias=dias)
        except Exception as e:
            logger.error(f"Erro ao obter resumo: {e}", exc_info=True)
            return None
    
    def _render_resumo(self, resumo: Dict[str, Any]) -> None:
        """Renderiza resumo completo com isolamento de falhas."""
        # Alertas no topo
        self._render_alertas(resumo.get("alertas", []))
        
        # Métricas rápidas
        metrics = self._calculate_metrics(resumo)
        self._render_metrics(metrics)
        
        # Detalhes por seção (cada uma com seu próprio try-except)
        self._render_secao_peso(resumo.get("peso", {}))
        self._render_secao_nutricao(resumo.get("nutricao", {}))
        self._render_secao_habitos(resumo.get("habitos", {}))
        self._render_secao_checkins(resumo.get("checkins", {}))
        self._render_secao_metas(resumo.get("metas", []))
        self._render_secao_condutas(resumo.get("condutas", []))
        self._render_secao_xp(resumo.get("xp", {}))
    
    def _render_alertas(self, alertas: List[Dict]) -> None:
        """Renderiza alertas com validação."""
        try:
            if not alertas or not isinstance(alertas, list):
                return
            
            for alerta in alertas:
                if not isinstance(alerta, dict):
                    continue
                
                self._render_alerta_item(alerta)
        except Exception as e:
            logger.error(f"Erro ao renderizar alertas: {e}", exc_info=True)
    
    def _render_alerta_item(self, alerta: Dict) -> None:
        """Renderiza item de alerta individual."""
        try:
            gravidade = self._parse_int(alerta.get("gravidade", 1))
            tipo = self._get_tipo_alerta(gravidade)
            titulo = alerta.get("titulo", "—")
            
            alert(f"⚠️ {titulo} (gravidade {gravidade}/3)", tipo)
        except Exception as e:
            logger.error(f"Erro ao renderizar alerta item: {e}", exc_info=True)
    
    def _get_tipo_alerta(self, gravidade: int) -> str:
        """Retorna tipo de alerta baseado na gravidade."""
        if gravidade >= GRAVIDADE_ERRO:
            return "error"
        elif gravidade >= GRAVIDADE_WARNING:
            return "warning"
        return "info"
    
    def _calculate_metrics(self, resumo: Dict) -> SummaryMetrics:
        """Calcula métricas do resumo com tratamento de erros."""
        try:
            peso = resumo.get("peso", {})
            hab = resumo.get("habitos", {})
            ci = resumo.get("checkins", {})
            periodo = resumo.get("periodo", {})
            dias_periodo = self._parse_int(periodo.get("dias", 30))
            
            return SummaryMetrics(
                variacao_peso=self._parse_float_optional(peso.get("variacao")),
                aderencia=self._parse_float(hab.get("media_aderencia", 0)),
                total_checkins=self._parse_int(ci.get("total", 0)),
                pct_checkins=self._calcular_pct_checkins(ci, dias_periodo),
                total_refeicoes=self._parse_int(resumo.get("nutricao", {}).get("total_refeicoes", 0)),
                pct_dias_registro=self._parse_int(resumo.get("nutricao", {}).get("pct_dias_registro", 0)),
                streak=self._parse_int(ci.get("streak_maximo", 0)),
                xp=self._parse_int(resumo.get("xp", {}).get("total", 0)),
                badges=self._parse_int(resumo.get("xp", {}).get("badges", 0)),
            )
        except Exception as e:
            logger.error(f"Erro ao calcular métricas: {e}", exc_info=True)
            return SummaryMetrics()
    
    def _calcular_pct_checkins(self, ci: Dict, dias_periodo: int) -> int:
        """Calcula percentual de check-ins com proteção contra divisão por zero."""
        try:
            total = self._parse_int(ci.get("total", 0))
            
            if dias_periodo <= 0:
                return 0
            
            return round(total / dias_periodo * 100)
        except Exception as e:
            logger.debug(f"Erro ao calcular pct checkins: {e}")
            return 0
    
    def _render_metrics(self, metrics: SummaryMetrics) -> None:
        """Renderiza métricas rápidas."""
        try:
            self._render_header_secao("Visão Geral")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                self._render_metric_variacao_peso(metrics.variacao_peso)
            
            with col2:
                self._render_metric_aderencia(metrics.aderencia)
            
            with col3:
                self._render_metric_checkins(metrics.total_checkins, metrics.pct_checkins)
            
            with col4:
                self._render_metric_refeicoes(metrics.total_refeicoes, metrics.pct_dias_registro)
        except Exception as e:
            logger.error(f"Erro ao renderizar métricas: {e}", exc_info=True)
    
    def _render_header_secao(self, titulo: str) -> None:
        """Renderiza cabeçalho de seção."""
        st.markdown(
            f"""
            <p style="font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em;
                color: var(--text-faint); text-transform: uppercase; margin: 1.1rem 0 0.6rem;">
                {titulo}
            </p>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_metric_variacao_peso(self, variacao: Optional[float]) -> None:
        """Renderiza métrica de variação de peso."""
        if variacao is not None:
            sinal = "▼" if variacao < 0 else "▲"
            cor = "success" if variacao <= 0 else "warning"
            metric_card(f"{sinal} {abs(variacao):.1f}kg", "Variação de peso", "⚖️", cor)
        else:
            metric_card(DEFAULT_METRIC_VALUE, "Sem pesagens", "⚖️")
    
    def _render_metric_aderencia(self, aderencia: float) -> None:
        """Renderiza métrica de aderência."""
        cor = self._get_cor_aderencia(aderencia)
        metric_card(f"{aderencia:.0f}%", "Aderência hábitos", "📋", cor)
    
    def _get_cor_aderencia(self, aderencia: float) -> str:
        """Retorna cor baseada na aderência."""
        if aderencia >= ADERENCIA_SUCESSO:
            return "success"
        elif aderencia >= ADERENCIA_ALERTA:
            return "warning"
        return "error"
    
    def _render_metric_checkins(self, total: int, pct: int) -> None:
        """Renderiza métrica de check-ins."""
        cor = self._get_cor_checkins(pct)
        metric_card(f"{total} check-ins ({pct}%)", "Check-ins", "✅", cor)
    
    def _get_cor_checkins(self, pct: int) -> str:
        """Retorna cor baseada no percentual de check-ins."""
        if pct >= PCT_CHECKIN_SUCESSO:
            return "success"
        elif pct >= PCT_CHECKIN_ALERTA:
            return "warning"
        return "error"
    
    def _render_metric_refeicoes(self, total: int, pct_dias: int) -> None:
        """Renderiza métrica de refeições."""
        metric_card(
            f"{total} refeições",
            f"{pct_dias}% dias com registro",
            "🍽️",
        )
    
    def _render_secao_peso(self, peso: Dict) -> None:
        """Renderiza seção de peso com tratamento de erros."""
        try:
            if not peso or not isinstance(peso, dict):
                return
            
            divider()
            st.markdown("##### ⚖️ Evolução de Peso")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                self._render_metric_peso_atual(peso)
            
            with col2:
                self._render_metric_peso_inicial(peso)
            
            with col3:
                self._render_metric_variacao(peso)
        except Exception as e:
            logger.error(f"Erro ao renderizar seção peso: {e}", exc_info=True)
    
    def _render_metric_peso_atual(self, peso: Dict) -> None:
        """Renderiza métrica de peso atual."""
        atual = peso.get("atual")
        valor = f"{atual} kg" if atual else DEFAULT_METRIC_VALUE
        metric_card(valor, "Peso atual", "⚖️")
    
    def _render_metric_peso_inicial(self, peso: Dict) -> None:
        """Renderiza métrica de peso inicial."""
        inicial = peso.get("inicial")
        valor = f"{inicial} kg" if inicial else DEFAULT_METRIC_VALUE
        metric_card(valor, "Peso inicial do período", "📊")
    
    def _render_metric_variacao(self, peso: Dict) -> None:
        """Renderiza métrica de variação."""
        var = self._parse_float_optional(peso.get("variacao"))
        
        if var is not None:
            cor = "success" if var < 0 else "warning"
            metric_card(f"{var:+.1f} kg", "Variação", "📉", cor)
        else:
            metric_card(DEFAULT_METRIC_VALUE, "Variação", "📉")
    
    def _render_secao_nutricao(self, nutricao: Dict) -> None:
        """Renderiza seção de nutrição com tratamento de erros."""
        try:
            if not nutricao or not isinstance(nutricao, dict):
                return
            
            divider()
            st.markdown("##### 🍽️ Nutrição")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                media_cal = self._parse_float(nutricao.get("media_calorias", 0))
                metric_card(f"{media_cal:.0f} kcal", "Média diária", "🔥")
            
            with col2:
                media_prot = self._parse_float(nutricao.get("media_proteina", 0))
                metric_card(f"{media_prot:.0f}g", "Proteína média", "🥩")
            
            with col3:
                pct_dias = self._parse_int(nutricao.get("pct_dias_registro", 0))
                metric_card(f"{pct_dias}%", "Dias com registro", "📅")
        except Exception as e:
            logger.error(f"Erro ao renderizar seção nutrição: {e}", exc_info=True)
    
    def _render_secao_habitos(self, habitos: Dict) -> None:
        """Renderiza seção de hábitos com tratamento de erros."""
        try:
            if not habitos or not isinstance(habitos, dict):
                return
            
            divider()
            st.markdown("##### 📋 Hábitos")
            
            media_aderencia = self._parse_float(habitos.get("media_aderencia", 0))
            streak_maximo = self._parse_int(habitos.get("streak_maximo", 0))
            
            st.markdown(
                f"""
                <div style="display: flex; gap: 1.2rem; flex-wrap: wrap;">
                    <div>
                        <span style="font-size: 0.80rem; color: var(--text-muted);">
                            Aderência média:
                        </span>
                        <span style="font-weight: 700; color: var(--text);">
                            {media_aderencia:.0f}%
                        </span>
                    </div>
                    <div>
                        <span style="font-size: 0.80rem; color: var(--text-muted);">
                            Streak máximo:
                        </span>
                        <span style="font-weight: 700; color: var(--text);">
                            {streak_maximo} dias
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar seção hábitos: {e}", exc_info=True)
    
    def _render_secao_checkins(self, checkins: Dict) -> None:
        """Renderiza seção de check-ins com tratamento de erros."""
        try:
            if not checkins or not isinstance(checkins, dict):
                return
            
            divider()
            st.markdown("##### 💭 Check-ins")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total = self._parse_int(checkins.get("total", 0))
                metric_card(str(total), "Total", "✅")
            
            with col2:
                humor = self._parse_float(checkins.get("humor_medio", 0))
                metric_card(f"{humor:.1f}/5", "Humor médio", "😊")
            
            with col3:
                energia = self._parse_float(checkins.get("energia_media", 0))
                metric_card(f"{energia:.1f}/5", "Energia média", "⚡")
        except Exception as e:
            logger.error(f"Erro ao renderizar seção check-ins: {e}", exc_info=True)
    
    def _render_secao_metas(self, metas: List[Dict]) -> None:
        """Renderiza seção de metas com tratamento de erros."""
        try:
            if not metas or not isinstance(metas, list):
                return
            
            divider()
            st.markdown("##### 🎯 Metas")
            
            for meta in metas[:MAX_METAS_EXIBIR]:
                if not isinstance(meta, dict):
                    continue
                self._render_meta_item(meta)
        except Exception as e:
            logger.error(f"Erro ao renderizar seção metas: {e}", exc_info=True)
    
    def _render_meta_item(self, meta: Dict) -> None:
        """Renderiza item de meta individual."""
        try:
            titulo = meta.get("titulo", "Meta")
            progresso = self._parse_int(meta.get("progresso", 0))
            concluida = meta.get("concluida", False)
            concluida_em = self._formatar_data(meta.get("concluida_em", ""))
            
            concluida_texto = f" · Concluída em {concluida_em}" if concluida and concluida_em else ""
            
            st.markdown(
                f"""
                <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle);">
                    <div style="font-weight: 600; color: var(--text); font-size: 0.92rem;">
                        {titulo}
                    </div>
                    <div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.15rem;">
                        Progresso: {progresso}%{concluida_texto}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar meta item: {e}", exc_info=True)
    
    def _render_secao_condutas(self, condutas: List[Dict]) -> None:
        """Renderiza seção de condutas com tratamento de erros."""
        try:
            if not condutas or not isinstance(condutas, list):
                return
            
            divider()
            st.markdown("##### 📋 Últimas Condutas")
            
            for conduta in condutas[:MAX_CONDUTAS_EXIBIR]:
                if not isinstance(conduta, dict):
                    continue
                self._render_conduta_item(conduta)
        except Exception as e:
            logger.error(f"Erro ao renderizar seção condutas: {e}", exc_info=True)
    
    def _render_conduta_item(self, conduta: Dict) -> None:
        """Renderiza item de conduta individual."""
        try:
            titulo = conduta.get("titulo", "Conduta")
            descricao = conduta.get("descricao", "")
            data = self._formatar_data(conduta.get("data_conduta", ""))
            
            st.markdown(
                f"""
                <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle);">
                    <div style="font-weight: 600; color: var(--text); font-size: 0.92rem;">
                        {titulo}
                    </div>
                    <div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.15rem;">
                        {descricao}
                        <span style="margin-left: 0.6rem;">· {data}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar conduta item: {e}", exc_info=True)
    
    def _render_secao_xp(self, xp: Dict) -> None:
        """Renderiza seção de XP com tratamento de erros."""
        try:
            if not xp or not isinstance(xp, dict):
                return
            
            divider()
            st.markdown("##### ⭐ Gamificação")
            
            col1, col2 = st.columns(2)
            
            with col1:
                total_xp = self._parse_int(xp.get("total", 0))
                metric_card(str(total_xp), "XP Total", "⭐")
            
            with col2:
                badges = self._parse_int(xp.get("badges", 0))
                metric_card(str(badges), "Badges", "🏅")
        except Exception as e:
            logger.error(f"Erro ao renderizar seção XP: {e}", exc_info=True)
    
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
    
    def _parse_float_optional(self, value: Any) -> Optional[float]:
        """Converte valor para float opcional de forma segura."""
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None
    
    def _formatar_data(self, data_raw: Any) -> str:
        """Formata data de forma segura."""
        try:
            if not data_raw:
                return ""
            return str(data_raw)[:10]
        except Exception as e:
            logger.debug(f"Erro ao formatar data: {e}")
            return ""


# Função principal de compatibilidade
def render(services: Dict[str, Any], professional, paciente: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = ConsultationSummaryRenderer(services, professional, paciente)
    renderer.render()
