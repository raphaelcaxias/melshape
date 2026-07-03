"""
Melshape — Detalhe do Paciente: score, conquistas e helpers.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging

from views.components.cards import empty_state, metric_card, achievement_card

logger = logging.getLogger("Melshape.PatientDetailTabs")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limiares de score
SCORE_SUCESSO = 70.0
SCORE_ALERTA = 40.0

# Limites de query
LIMIT_SCORE = 1
LIMIT_CONQUISTAS = 50
LIMIT_QUERY_GENERICA = 200

# Cores do gauge
CORES_GAUGE = {
    "baixo": "rgba(220,38,38,0.15)",      # 0-40
    "medio": "rgba(217,119,6,0.15)",      # 40-70
    "alto": "rgba(22,163,74,0.15)",       # 70-100
    "barra": "#C9A84C",
    "threshold": "#C9A84C",
}

# Configurações de layout
LAYOUT_CONFIG = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "font_color": "#6B6B6B",
}

# Componentes do score
COMPONENTES_SCORE = [
    ("📋 Aderência", "peso_aderencia"),
    ("🔥 Engajamento", "peso_engajamento"),
    ("🍽️ Nutrição", "peso_nutricao"),
    ("💭 Comportamento", "peso_comportamento"),
    ("🩺 Clínico", "peso_clinico"),
]

# Pesos padrão dos componentes
PESO_ADERENCIA_DEFAULT = 25.0
PESO_ENGAJAMENTO_DEFAULT = 20.0
PESO_NUTRICAO_DEFAULT = 20.0
PESO_COMPORTAMENTO_DEFAULT = 15.0
PESO_CLINICO_DEFAULT = 20.0

# Fallbacks
DEFAULT_SCORE_VALUE = 0.0
DEFAULT_DATA = "—"
DEFAULT_BADGE = "—"


@dataclass
class ScoreData:
    """Dados do score de transformação."""
    score_global: float = DEFAULT_SCORE_VALUE
    peso_aderencia: float = PESO_ADERENCIA_DEFAULT
    peso_engajamento: float = PESO_ENGAJAMENTO_DEFAULT
    peso_nutricao: float = PESO_NUTRICAO_DEFAULT
    peso_comportamento: float = PESO_COMPORTAMENTO_DEFAULT
    peso_clinico: float = PESO_CLINICO_DEFAULT


class PatientDetailTabsRenderer:
    """Renderer dedicado para tabs do paciente."""
    
    def __init__(self, db):
        self.db = db
    
    def render_score(self, perfil_id: str) -> None:
        """Renderiza tab de score com tratamento de erros."""
        try:
            score_data = self._get_score(perfil_id)
            
            if not score_data or score_data.score_global == 0:
                empty_state(
                    "🏆",
                    "Score não disponível",
                    "O paciente precisa de mais registros para gerar o score",
                )
                return
            
            cor = self._get_cor_score(score_data.score_global)
            
            metric_card(
                f"{score_data.score_global:.0f}/100",
                "Score de Transformação",
                "🏆",
                cor,
            )
            
            # Gauge chart
            self._render_score_gauge(score_data.score_global)
            
            # Detalhamento do score
            self._render_score_detalhamento(score_data)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab score: {e}", exc_info=True)
            st.error("❌ Erro ao carregar score de transformação.")
    
    def _get_cor_score(self, score: float) -> str:
        """Retorna cor baseada no score."""
        if score >= SCORE_SUCESSO:
            return "success"
        elif score >= SCORE_ALERTA:
            return "warning"
        return "error"
    
    @st.cache_data(ttl=60)
    def _get_score(_self, perfil_id: str) -> Optional[ScoreData]:
        """Obtém dados do score com cache e tratamento de erros."""
        if not _self._is_real_db():
            return None
        
        try:
            response = (
                _self.db.client
                .table("vw_score_transformacao")
                .select("score_global")
                .eq("perfil_id", perfil_id)
                .limit(LIMIT_SCORE)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                row = response.data[0]
                return _self._parse_score_row(row)
        except Exception as e:
            logger.error(f"Erro ao buscar score do perfil {perfil_id}: {e}", exc_info=True)
        
        return None
    
    def _parse_score_row(self, row: Dict) -> ScoreData:
        """Parseia linha de score com segurança."""
        try:
            score_global = _parse_float(row.get("score_global"))
            return ScoreData(score_global=score_global)
        except Exception as e:
            logger.error(f"Erro ao parsear score row: {e}", exc_info=True)
            return ScoreData()
    
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
    
    def _render_score_gauge(self, score: float) -> None:
        """Renderiza gráfico gauge do score com proteção contra ImportError."""
        try:
            import plotly.graph_objects as go
            
            fig = self._build_gauge_figure(go, score)
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            logger.warning("Plotly não disponível para renderizar gauge")
            self._render_gauge_fallback(score)
        except Exception as e:
            logger.error(f"Erro ao renderizar gauge: {e}", exc_info=True)
            self._render_gauge_fallback(score)
    
    def _build_gauge_figure(self, go, score: float):
        """Constrói figura Plotly do gauge."""
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": CORES_GAUGE["barra"]},
                "steps": [
                    {"range": [0, 40], "color": CORES_GAUGE["baixo"]},
                    {"range": [40, 70], "color": CORES_GAUGE["medio"]},
                    {"range": [70, 100], "color": CORES_GAUGE["alto"]},
                ],
                "threshold": {
                    "line": {"color": CORES_GAUGE["threshold"], "width": 3},
                    "thickness": 0.75,
                    "value": score,
                },
            },
            title={"text": "Score Global de Transformação"},
        ))
        
        fig.update_layout(
            paper_bgcolor=LAYOUT_CONFIG["paper_bgcolor"],
            font_color=LAYOUT_CONFIG["font_color"],
            height=280,
            margin=dict(t=30, b=10, l=10, r=10),
        )
        
        return fig
    
    def _render_gauge_fallback(self, score: float) -> None:
        """Renderiza fallback quando Plotly não está disponível."""
        cor = self._get_cor_score(score)
        cor_css = f"var(--{cor})"
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="text-align: center;">
                <div style="font-size: 0.78rem; color: var(--text-muted);
                    text-transform: uppercase; letter-spacing: 0.08em;">
                    Score Global de Transformação
                </div>
                <div style="font-size: 2.5rem; font-weight: 800; color: {cor_css};
                    margin: 0.5rem 0;">
                    {score:.0f}
                </div>
                <div style="font-size: 0.82rem; color: var(--text-muted);">
                    de 100 pontos
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_score_detalhamento(self, score_data: ScoreData) -> None:
        """Renderiza detalhamento do score."""
        try:
            st.markdown(
                """
                <div style="font-size: 0.84rem; color: var(--text-muted); margin-top: 0.6rem;">
                    Score calculado por:
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            for label, attr_name in COMPONENTES_SCORE:
                peso = self._get_peso_componente(score_data, attr_name)
                self._render_componente_barra(label, peso)
        except Exception as e:
            logger.error(f"Erro ao renderizar detalhamento do score: {e}", exc_info=True)
    
    def _get_peso_componente(self, score_data: ScoreData, attr_name: str) -> float:
        """Obtém peso do componente com fallback."""
        try:
            return float(getattr(score_data, attr_name, 0.0))
        except (ValueError, TypeError):
            return 0.0
    
    def _render_componente_barra(self, label: str, peso: float) -> None:
        """Renderiza barra de componente do score."""
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 0.6rem;
                margin-bottom: 0.35rem;">
                <span style="font-size: 0.80rem; color: var(--text-muted);
                    width: 130px;">{label}</span>
                <div class="progress-track" style="flex: 1;">
                    <div class="progress-fill" style="width: {peso}%;"></div>
                </div>
                <span style="font-size: 0.76rem; color: var(--text-faint);
                    width: 45px; text-align: right;">{peso:.0f}%</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def render_conquistas(self, perfil_id: str) -> None:
        """Renderiza tab de conquistas com tratamento de erros."""
        try:
            conquistas = self._get_conquistas(perfil_id)
            
            if not conquistas:
                empty_state(
                    "🎖️",
                    "Nenhuma conquista ainda",
                    "O paciente ainda não desbloqueou badges",
                )
                return
            
            self._render_header_conquistas(len(conquistas))
            
            self._render_lista_conquistas(conquistas)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab conquistas: {e}", exc_info=True)
            st.error("❌ Erro ao carregar conquistas.")
    
    def _render_header_conquistas(self, total: int) -> None:
        """Renderiza cabeçalho de conquistas."""
        metric_card(str(total), "Conquistas desbloqueadas", "🏅")
        st.markdown("<br>", unsafe_allow_html=True)
    
    def _render_lista_conquistas(self, conquistas: List[Dict]) -> None:
        """Renderiza lista de conquistas em grid."""
        cols = st.columns(2)
        
        for i, conquista in enumerate(conquistas):
            with cols[i % 2]:
                self._render_conquista_item(conquista)
    
    def _render_conquista_item(self, conquista: Dict) -> None:
        """Renderiza item de conquista com tratamento de erros."""
        try:
            if not isinstance(conquista, dict):
                return
            
            badge = conquista.get("badge", DEFAULT_BADGE)
            data_str = self._formatar_data(conquista.get("conquistado_em", ""))
            
            achievement_card(badge, data_str)
        except Exception as e:
            logger.error(f"Erro ao renderizar conquista item: {e}", exc_info=True)
    
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
    def _get_conquistas(_self, perfil_id: str) -> List[Dict]:
        """Busca conquistas do paciente com cache e tratamento de erros."""
        if not _self._is_real_db():
            return []
        
        try:
            response = (
                _self.db.client
                .table("vw_conquistas_usuario")
                .select("badge,categoria,conquistado_em")
                .eq("perfil_id", perfil_id)
                .limit(LIMIT_CONQUISTAS)
                .execute()
            )
            
            data = response.data or []
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar conquistas do perfil {perfil_id}: {e}", exc_info=True)
            return []


# ── HELPERS ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def _get_perfil(db, nome: str) -> Dict:
    """Busca perfil pelo nome com cache e tratamento de erros."""
    if not nome:
        return {}
    
    # Banco real
    if _is_real_db(db):
        try:
            response = (
                db.client
                .table("perfis")
                .select("id, nome_completo, tipo_jornada, peso_atual")
                .ilike("nome_completo", f"%{nome}%")
                .limit(LIMIT_SCORE)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                return response.data[0]
        except Exception as e:
            logger.error(f"Erro ao buscar perfil '{nome}': {e}", exc_info=True)
    
    # Fallback mock
    return _get_perfil_mock(db, nome)


def _get_perfil_mock(db, nome: str) -> Dict:
    """Busca perfil no mock com tratamento de erros."""
    try:
        mock_data = db._mock().get("users", {})
        for user in mock_data.values():
            if nome.lower() in user.get("name", "").lower():
                return {
                    "id": user.get("email"),
                    "nome_completo": user.get("name", ""),
                }
    except Exception as e:
        logger.error(f"Erro ao buscar perfil mock '{nome}': {e}", exc_info=True)
    
    return {}


def _is_real_db(db) -> bool:
    """Verifica se o banco é real (não mock)."""
    try:
        return (
            hasattr(db, "is_real") and
            db.is_real and
            hasattr(db, "client")
        )
    except Exception as e:
        logger.debug(f"Erro ao verificar banco real: {e}")
        return False


@st.cache_data(ttl=60)
def _query_perfil(db, tabela: str, colunas: str,
                  perfil_id: str, ordem: str = "") -> List[Dict]:
    """Executa query no Supabase para um perfil específico com cache."""
    if not _is_real_db(db):
        return []
    
    try:
        query = (
            db.client
            .table(tabela)
            .select(colunas)
            .eq("perfil_id", perfil_id)
        )
        
        if ordem:
            query = query.order(ordem)
        
        response = query.limit(LIMIT_QUERY_GENERICA).execute()
        data = response.data or []
        
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Erro ao executar query em '{tabela}': {e}", exc_info=True)
        return []


def _parse_float(value: Any) -> float:
    """Converte valor para float de forma segura."""
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


# Funções de compatibilidade
def _tab_score(db, perfil_id: str) -> None:
    """Renderiza tab de score (compatibilidade)."""
    try:
        renderer = PatientDetailTabsRenderer(db)
        renderer.render_score(perfil_id)
    except Exception as e:
        logger.error(f"Erro ao renderizar tab score: {e}", exc_info=True)
        st.error("❌ Erro ao carregar score.")


def _tab_conquistas(db, perfil_id: str) -> None:
    """Renderiza tab de conquistas (compatibilidade)."""
    try:
        renderer = PatientDetailTabsRenderer(db)
        renderer.render_conquistas(perfil_id)
    except Exception as e:
        logger.error(f"Erro ao renderizar tab conquistas: {e}", exc_info=True)
        st.error("❌ Erro ao carregar conquistas.")
