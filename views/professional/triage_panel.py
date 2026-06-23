"""
Melshape — Painel de Triagem Profissional.

Views usadas:
  vw_prioridade_intervencao → score ponderado por risco + engajamento
  vw_alertas_prioritarios   → alertas não visualizados por prioridade

Princípio: toda linha deve responder
"O que devo fazer com este paciente agora?"
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from views.components.cards import empty_state, section_header, divider, metric_card

logger = logging.getLogger("Melshape.Triage")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limiares de score
SCORE_URGENTE = 70.0
SCORE_ALTA = 40.0

# Limiares de prioridade
PRIORIDADE_CRITICA = 8
PRIORIDADE_ALTA = 5

# Limites
LIMIT_QUERY = 50
MAX_PACIENTES_EXIBIR = 20

# Cores
COR_URGENTE = "var(--error)"
COR_ALTA = "var(--warning)"
COR_NORMAL = "var(--success)"
COR_INFO = "var(--info)"

# Fallbacks
DEFAULT_NOME = "—"
DEFAULT_DATA = "—"
DEFAULT_CATEGORIA = "—"
DEFAULT_TITULO = ""

# Chaves de session state
SESSION_KEY_SELECTED_PATIENT = "pro_selected_patient"
SESSION_KEY_PAGE = "page"
PAGE_PATIENT_DETAIL = "pro_patient_detail"


@dataclass
class TriagePatient:
    """Paciente na fila de triagem."""
    id: str
    nome: str
    risco_abandono: float
    score_engajamento: float
    score_adesao: float
    score_prioridade: float


@dataclass
class PriorityAlert:
    """Alerta prioritário."""
    nome: str
    categoria: str
    titulo: str
    prioridade: int
    data: str


class TriagePanelRenderer:
    """Renderer dedicado para painel de triagem."""
    
    def __init__(self, services: Dict[str, Any]):
        self.services = services or {}
        self.db = services.get("db")
    
    def render(self) -> None:
        """Renderiza painel de triagem com tratamento de erros."""
        try:
            section_header(
                "🎯 Triagem de Pacientes",
                "Prioridade calculada por risco, engajamento e adesão",
            )
            
            # Tabs
            self._render_tabs()
        except Exception as e:
            logger.error(f"Erro ao renderizar painel de triagem: {e}", exc_info=True)
            st.error("❌ Erro ao carregar painel de triagem.")
    
    def _render_tabs(self) -> None:
        """Renderiza as 2 tabs com isolamento de falhas."""
        tab_prioridade, tab_alertas = st.tabs([
            "📊 Fila por Prioridade",
            "🚨 Alertas Prioritários",
        ])
        
        with tab_prioridade:
            self._render_tab_prioridade()
        
        with tab_alertas:
            self._render_tab_alertas()
    
    def _render_tab_prioridade(self) -> None:
        """Renderiza tab de prioridade com tratamento de erros."""
        try:
            self._render_prioridade()
        except Exception as e:
            logger.error(f"Erro ao renderizar tab prioridade: {e}", exc_info=True)
            st.error("❌ Erro ao carregar fila por prioridade.")
    
    def _render_tab_alertas(self) -> None:
        """Renderiza tab de alertas com tratamento de erros."""
        try:
            self._render_alertas_prioritarios()
        except Exception as e:
            logger.error(f"Erro ao renderizar tab alertas: {e}", exc_info=True)
            st.error("❌ Erro ao carregar alertas prioritários.")
    
    def _render_prioridade(self) -> None:
        """Renderiza fila por prioridade."""
        pacientes = self._get_pacientes_prioridade()
        
        if not pacientes:
            empty_state(
                "🎯",
                "Sem pacientes para triagem",
                "Os dados aparecem conforme os pacientes usam o sistema",
            )
            return
        
        self._render_header_pacientes(len(pacientes))
        
        for i, paciente in enumerate(pacientes[:MAX_PACIENTES_EXIBIR]):
            self._render_paciente_item(i, paciente)
    
    @st.cache_data(ttl=60)
    def _get_pacientes_prioridade(_self) -> List[Dict]:
        """Obtém pacientes ordenados por prioridade (com cache)."""
        return _self._query_view(
            "vw_prioridade_intervencao",
            "id, nome_completo, risco_abandono, score_engajamento, "
            "score_adesao, score_prioridade",
            order_col="score_prioridade",
        )
    
    def _render_header_pacientes(self, total: int) -> None:
        """Renderiza cabeçalho da lista de pacientes."""
        st.markdown(
            f"""
            <div style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 0.9rem;">
                <b>{total}</b> paciente(s) · ordenados por prioridade
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_paciente_item(self, idx: int, paciente: Dict) -> None:
        """Renderiza um item da lista de pacientes com tratamento de erros."""
        try:
            if not isinstance(paciente, dict):
                return
            
            nome = paciente.get("nome_completo", DEFAULT_NOME)
            score = self._parse_float(paciente.get("score_prioridade"))
            risco = self._parse_float(paciente.get("risco_abandono"))
            engajamento = self._parse_float(paciente.get("score_engajamento"))
            adesao = self._parse_float(paciente.get("score_adesao"))
            
            cor_score = self._get_cor_score(score)
            urgencia = self._get_urgencia(score)
            
            self._render_card_paciente(idx, nome, score, risco, engajamento, adesao, cor_score, urgencia)
            self._render_botao_ver_paciente(idx, nome)
        except Exception as e:
            logger.error(f"Erro ao renderizar paciente item #{idx}: {e}", exc_info=True)
    
    def _get_cor_score(self, score: float) -> str:
        """Retorna cor baseada no score."""
        if score >= SCORE_URGENTE:
            return COR_URGENTE
        elif score >= SCORE_ALTA:
            return COR_ALTA
        return COR_NORMAL
    
    def _get_urgencia(self, score: float) -> str:
        """Retorna label de urgência baseado no score."""
        if score >= SCORE_URGENTE:
            return "🚨 URGENTE"
        elif score >= SCORE_ALTA:
            return "⚠️ ALTA"
        return "📋 NORMAL"
    
    def _render_card_paciente(
        self,
        idx: int,
        nome: str,
        score: float,
        risco: float,
        engajamento: float,
        adesao: float,
        cor_score: str,
        urgencia: str,
    ) -> None:
        """Renderiza card do paciente."""
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between;
                align-items: center; padding: 0.75rem 0.95rem;
                border: 1px solid var(--border); border-radius: 12px;
                margin-bottom: 0.5rem; background: var(--surface);">
                <div style="flex: 1;">
                    <div style="font-weight: 700; font-size: 0.94rem; color: var(--text);">
                        #{idx + 1} {nome}
                    </div>
                    <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem;">
                        Risco: {risco:.0f}% · Eng: {engajamento:.0f}% · Ades: {adesao:.0f}%
                    </div>
                </div>
                <div style="text-align: right; margin-left: 0.9rem;">
                    <div style="font-size: 1.3rem; font-weight: 800; color: {cor_score};">
                        {score:.0f}
                    </div>
                    <div style="font-size: 0.72rem; color: {cor_score};">
                        {urgencia}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_botao_ver_paciente(self, idx: int, nome: str) -> None:
        """Renderiza botão para ver paciente."""
        if st.button(
            "Ver paciente →",
            key=f"triage_{idx}_{nome}",
            use_container_width=True,
        ):
            self._navegar_para_paciente(nome)
    
    def _navegar_para_paciente(self, nome: str) -> None:
        """Navega para detalhe do paciente com tratamento de erros."""
        try:
            st.session_state[SESSION_KEY_SELECTED_PATIENT] = nome
            st.session_state[SESSION_KEY_PAGE] = PAGE_PATIENT_DETAIL
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para paciente '{nome}': {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")
    
    def _render_alertas_prioritarios(self) -> None:
        """Renderiza alertas prioritários."""
        alertas = self._get_alertas_prioritarios()
        
        if not alertas:
            self._render_sem_alertas()
            return
        
        self._render_header_alertas(len(alertas))
        
        for alerta in alertas:
            self._render_alerta_item(alerta)
    
    @st.cache_data(ttl=60)
    def _get_alertas_prioritarios(_self) -> List[Dict]:
        """Obtém alertas prioritários (com cache)."""
        return _self._query_view(
            "vw_alertas_prioritarios",
            "nome_completo, categoria, titulo, prioridade, criado_em",
            order_col="prioridade",
        )
    
    def _render_sem_alertas(self) -> None:
        """Renderiza mensagem quando não há alertas."""
        st.markdown(
            """
            <div class="alert-success" style="margin: 0.5rem 0;">
                ✅ Nenhum alerta prioritário aberto
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_header_alertas(self, total: int) -> None:
        """Renderiza cabeçalho da lista de alertas."""
        st.markdown(
            f"""
            <div style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 0.9rem;">
                <b>{total}</b> alerta(s) não visualizado(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_alerta_item(self, alerta: Dict) -> None:
        """Renderiza um item de alerta com tratamento de erros."""
        try:
            if not isinstance(alerta, dict):
                return
            
            prioridade = self._parse_int(alerta.get("prioridade"))
            cor = self._get_cor_prioridade(prioridade)
            data = self._formatar_data(alerta.get("criado_em", ""))
            
            nome = alerta.get("nome_completo", DEFAULT_NOME)
            titulo = alerta.get("titulo", DEFAULT_TITULO)
            categoria = alerta.get("categoria", DEFAULT_CATEGORIA)
            
            self._render_card_alerta(nome, titulo, categoria, data, cor, prioridade)
        except Exception as e:
            logger.error(f"Erro ao renderizar alerta item: {e}", exc_info=True)
    
    def _get_cor_prioridade(self, prioridade: int) -> str:
        """Retorna cor baseada na prioridade."""
        if prioridade >= PRIORIDADE_CRITICA:
            return COR_URGENTE
        elif prioridade >= PRIORIDADE_ALTA:
            return COR_ALTA
        return COR_INFO
    
    def _render_card_alerta(
        self,
        nome: str,
        titulo: str,
        categoria: str,
        data: str,
        cor: str,
        prioridade: int,
    ) -> None:
        """Renderiza card de alerta."""
        st.markdown(
            f"""
            <div style="display: flex; gap: 0.8rem; align-items: flex-start;
                padding: 0.7rem 0; border-bottom: 1px solid var(--border-subtle);">
                <div style="width: 4px; background: {cor};
                    border-radius: 2px; flex-shrink: 0; align-self: stretch;">
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 0.92rem; color: var(--text);">
                        {nome}
                    </div>
                    <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.15rem;">
                        {titulo}
                    </div>
                    <div style="font-size: 0.74rem; color: var(--text-faint); margin-top: 0.15rem;">
                        {categoria} · {data}
                    </div>
                </div>
                <div style="font-size: 1.05rem; font-weight: 800; color: {cor};">
                    P{prioridade}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    @st.cache_data(ttl=60)
    def _query_view(_self, view: str, colunas: str, order_col: str = "prioridade") -> List[Dict]:
        """Executa query em uma view do Supabase com cache e tratamento de erros."""
        if not _self._is_real_db():
            return []
        
        try:
            response = (
                _self.db.client
                .table(view)
                .select(colunas)
                .order(order_col, desc=True)
                .limit(LIMIT_QUERY)
                .execute()
            )
            
            data = response.data or []
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Erro ao executar query em '{view}': {e}", exc_info=True)
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
    
    def _parse_float(self, value: Any) -> float:
        """Converte valor para float de forma segura."""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _formatar_data(self, data_raw: Any) -> str:
        """Formata data de forma segura."""
        try:
            if not data_raw:
                return DEFAULT_DATA
            return str(data_raw)[:10]
        except Exception as e:
            logger.debug(f"Erro ao formatar data: {e}")
            return DEFAULT_DATA


# Função principal de compatibilidade
def render_triagem(services: Dict[str, Any]) -> None:
    """Renderiza painel de triagem (compatibilidade)."""
    try:
        renderer = TriagePanelRenderer(services)
        renderer.render()
    except Exception as e:
        logger.error(f"Erro ao renderizar triagem: {e}", exc_info=True)
        st.error("❌ Erro ao carregar painel de triagem.")
