"""
Melshape — Tela de Metas.

O paciente vê suas metas com progresso calculado
automaticamente a partir dos dados reais do banco.
Criação guiada por tipo com templates do pilar.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import date
import logging

from services.goals_service import GoalsService
from services.journey_service import JourneyService
from views.components.cards import (
    section_header, empty_state, metric_card,
    xp_toast, alert,
)
from views.patient.goals_form import render_form_meta

logger = logging.getLogger("Melshape.Goals")


@dataclass
class GoalStats:
    """Estatísticas de metas."""
    total: int = 0
    ativas: int = 0
    concluidas: int = 0


class GoalsRenderer:
    """Renderer dedicado para tela de metas."""
    
    # Constantes de XP
    XP_META_CONCLUIDA = 200
    
    # Constantes de limiares de progresso
    PROGRESSO_DESTAQUE = 75
    PROGRESSO_CONCLUIDA = 100
    
    # Constantes de prazo
    PRAZO_CRITICO = 3
    PRAZO_ALERTA = 7
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.svc = self._init_goals_service()
        self.jrn = self._init_journey_service()
        self.health_mode = user.get("health_mode", "general")
    
    def _init_goals_service(self) -> Optional[GoalsService]:
        """Inicializa GoalsService com tratamento de erros."""
        if not self.db:
            logger.error("Database não disponível para GoalsRenderer")
            return None
        
        try:
            return GoalsService(self.db)
        except Exception as e:
            logger.error(f"Erro ao inicializar GoalsService: {e}", exc_info=True)
            return None
    
    def _init_journey_service(self) -> Optional[JourneyService]:
        """Inicializa JourneyService com tratamento de erros."""
        if not self.db:
            logger.error("Database não disponível para GoalsRenderer")
            return None
        
        try:
            return JourneyService(self.db)
        except Exception as e:
            logger.error(f"Erro ao inicializar JourneyService: {e}", exc_info=True)
            return None
    
    def render(self) -> None:
        """Renderiza tela de metas."""
        section_header("🎯 Metas", "Objetivos concretos com progresso real")
        
        # Verifica se serviços foram inicializados
        if not self.svc or not self.jrn:
            self._render_error_state()
            return
        
        # Busca jornada ativa
        jornada = self._get_jornada()
        jornada_id = jornada.get("id", "") if jornada else ""
        
        # Busca metas
        metas = self._get_metas(jornada_id) if jornada_id else []
        
        # Bloco de estatísticas
        self._render_stats(metas)
        
        st.divider()
        
        # Tabs
        self._render_tabs(metas, jornada_id)
    
    def _render_error_state(self) -> None:
        """Renderiza estado de erro quando serviços não estão disponíveis."""
        alert(
            "❌ Não foi possível carregar o módulo de metas. "
            "Por favor, recarregue a página ou entre em contato com o suporte.",
            "error",
        )
    
    @st.cache_data(ttl=60)
    def _get_jornada(_self) -> Optional[Dict]:
        """Obtém jornada ativa (com cache)."""
        try:
            jornada = _self.jrn.garantir_jornada(_self.user)
            return jornada if jornada else None
        except Exception as e:
            logger.error(f"Erro ao buscar jornada: {e}", exc_info=True)
            return None
    
    @st.cache_data(ttl=60)
    def _get_metas(_self, jornada_id: str) -> List[Dict]:
        """Obtém metas da jornada (com cache)."""
        if not jornada_id:
            return []
        
        try:
            metas = _self.db.get_metas(jornada_id)
            return metas or []
        except Exception as e:
            logger.error(f"Erro ao buscar metas: {e}", exc_info=True)
            return []
    
    def _render_tabs(self, metas: List[Dict], jornada_id: str) -> None:
        """Renderiza as 3 tabs de metas."""
        tab_ativas, tab_concluidas, tab_nova = st.tabs([
            "⏳ Em Andamento",
            "✅ Concluídas",
            "➕ Nova Meta",
        ])
        
        with tab_ativas:
            self._render_tab_ativas(metas, jornada_id)
        
        with tab_concluidas:
            self._render_tab_concluidas(metas)
        
        with tab_nova:
            self._render_tab_nova(jornada_id)
    
    def _render_tab_ativas(self, metas: List[Dict], jornada_id: str) -> None:
        """Renderiza tab de metas ativas com tratamento de erros."""
        try:
            ativas = [m for m in metas if not m.get("concluida")]
            self._render_ativas(ativas, jornada_id)
        except Exception as e:
            logger.error(f"Erro ao renderizar metas ativas: {e}", exc_info=True)
            alert("❌ Erro ao carregar metas ativas.", "error")
    
    def _render_tab_concluidas(self, metas: List[Dict]) -> None:
        """Renderiza tab de metas concluídas com tratamento de erros."""
        try:
            concluidas = [m for m in metas if m.get("concluida")]
            self._render_concluidas(concluidas)
        except Exception as e:
            logger.error(f"Erro ao renderizar metas concluídas: {e}", exc_info=True)
            alert("❌ Erro ao carregar metas concluídas.", "error")
    
    def _render_tab_nova(self, jornada_id: str) -> None:
        """Renderiza tab de nova meta com tratamento de erros."""
        try:
            render_form_meta(self.db, self.svc, jornada_id, self.health_mode)
        except Exception as e:
            logger.error(f"Erro ao renderizar formulário de meta: {e}", exc_info=True)
            alert("❌ Erro ao carregar formulário de meta.", "error")
    
    def _render_stats(self, metas: List[Dict]) -> None:
        """Renderiza estatísticas de metas."""
        if not metas:
            return
        
        stats = self._calculate_stats(metas)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            metric_card(str(stats.total), "Metas totais", "🎯")
        
        with col2:
            cor = "warning" if stats.ativas > 0 else "success"
            metric_card(str(stats.ativas), "Em andamento", "⏳", cor)
        
        with col3:
            cor = "success" if stats.concluidas > 0 else ""
            metric_card(str(stats.concluidas), "Concluídas", "✅", cor)
    
    def _calculate_stats(self, metas: List[Dict]) -> GoalStats:
        """Calcula estatísticas das metas."""
        try:
            return GoalStats(
                total=len(metas),
                ativas=sum(1 for m in metas if not m.get("concluida")),
                concluidas=sum(1 for m in metas if m.get("concluida")),
            )
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            return GoalStats()
    
    def _render_ativas(self, metas: List[Dict], jornada_id: str) -> None:
        """Renderiza metas ativas."""
        if not metas:
            empty_state(
                "🎯",
                "Nenhuma meta ativa",
                "Crie sua primeira meta na aba 'Nova Meta'",
            )
            return
        
        for meta in metas:
            self._render_meta_card(meta, jornada_id, concluida=False)
    
    def _render_concluidas(self, metas: List[Dict]) -> None:
        """Renderiza metas concluídas."""
        if not metas:
            empty_state(
                "✅",
                "Nenhuma meta concluída ainda",
                "Continue avançando — você vai chegar lá",
            )
            return
        
        self._render_concluidas_header(len(metas))
        
        for meta in metas:
            self._render_meta_concluida(meta)
    
    def _render_concluidas_header(self, total: int) -> None:
        """Renderiza cabeçalho de metas concluídas."""
        st.markdown(
            f"""
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.8rem;">
                🏆 <b>{total}</b> meta(s) concluída(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_meta_card(self, meta: Dict[str, Any], jornada_id: str, 
                          concluida: bool) -> None:
        """Renderiza um card de meta."""
        progresso = self._calcular_progresso(meta)
        pct = progresso.get("pct", 0)
        titulo = meta.get("titulo", "Meta")
        tipo = meta.get("tipo", "livre")
        meta_id = meta.get("id", "")
        prazo = meta.get("prazo")
        
        icone, label = self._get_tipo_info(tipo)
        
        # Prazo
        prazo_html = self._render_prazo(prazo)
        
        # Cor da borda
        cor_borda = self._get_cor_borda(concluida, pct)
        cor_fill = self._get_cor_fill(pct)
        
        delta_label = progresso.get("delta_label", "")
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" 
                style="margin-bottom: 0.8rem; border-color: {cor_borda};">
                <div style="display: flex; justify-content: space-between;
                    align-items: flex-start; margin-bottom: 0.6rem;">
                    <div style="flex: 1;">
                        <div style="font-weight: 700; font-size: 0.96rem; color: var(--text);">
                            {icone} {titulo}
                        </div>
                        <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">
                            {label} · {delta_label}
                        </div>
                    </div>
                    <div style="text-align: right; margin-left: 1rem;">
                        <div style="font-size: 1.5rem; font-weight: 800; color: var(--primary);">
                            {pct}%
                        </div>
                        {prazo_html}
                    </div>
                </div>
                <div class="progress-track">
                    <div class="progress-fill {cor_fill}" style="width: {pct}%;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Botão de concluir (se 100% e não concluída)
        if pct >= self.PROGRESSO_CONCLUIDA and not concluida:
            self._render_botao_concluir(meta_id, titulo)
    
    def _calcular_progresso(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula progresso da meta com tratamento de erros."""
        try:
            progresso = self.svc.calcular_progresso(meta)
            return progresso if progresso else {"pct": 0, "delta_label": ""}
        except Exception as e:
            logger.error(f"Erro ao calcular progresso da meta: {e}")
            return {"pct": 0, "delta_label": ""}
    
    def _get_tipo_info(self, tipo: str) -> Tuple[str, str]:
        """Obtém ícone e label do tipo de meta."""
        try:
            tipo_labels = self.svc.tipo_labels()
            return tipo_labels.get(tipo, ("🎯", "Livre"))
        except Exception as e:
            logger.error(f"Erro ao obter tipo info: {e}")
            return ("🎯", "Livre")
    
    def _get_cor_borda(self, concluida: bool, pct: int) -> str:
        """Retorna cor da borda baseada no status da meta."""
        if concluida or pct >= self.PROGRESSO_CONCLUIDA:
            return "var(--success)"
        elif pct >= self.PROGRESSO_DESTAQUE:
            return "var(--primary)"
        else:
            return "var(--border)"
    
    def _get_cor_fill(self, pct: int) -> str:
        """Retorna classe CSS do fill da barra de progresso."""
        if pct < self.PROGRESSO_DESTAQUE:
            return ""
        elif pct < self.PROGRESSO_CONCLUIDA:
            return "warning"
        else:
            return "success"
    
    def _render_prazo(self, prazo: Optional[str]) -> str:
        """Renderiza informação de prazo."""
        if not prazo:
            return ""
        
        dias_restantes = self._calcular_dias_restantes(prazo)
        
        if dias_restantes is None:
            return ""
        
        cor = self._get_cor_prazo(dias_restantes)
        texto = self._get_texto_prazo(dias_restantes)
        
        return (
            f'<span style="font-size: 0.76rem; color: {cor}; margin-top: 0.2rem; display: block;">'
            f'{texto}</span>'
        )
    
    def _calcular_dias_restantes(self, prazo: str) -> Optional[int]:
        """Calcula dias restantes até o prazo."""
        try:
            prazo_date = date.fromisoformat(prazo[:10])
            return (prazo_date - date.today()).days
        except Exception as e:
            logger.debug(f"Erro ao calcular dias restantes: {e}")
            return None
    
    def _get_cor_prazo(self, dias_restantes: int) -> str:
        """Retorna cor baseada nos dias restantes."""
        if dias_restantes <= self.PRAZO_CRITICO:
            return "var(--error)"
        elif dias_restantes <= self.PRAZO_ALERTA:
            return "var(--warning)"
        else:
            return "var(--text-muted)"
    
    def _get_texto_prazo(self, dias_restantes: int) -> str:
        """Retorna texto do prazo."""
        if dias_restantes >= 0:
            return f"⏰ Vence em {dias_restantes}d"
        else:
            return "⚠️ Prazo vencido"
    
    def _render_botao_concluir(self, meta_id: str, titulo: str) -> None:
        """Renderiza botão de concluir meta."""
        if st.button(
            "🏆 Marcar como concluída",
            key=f"goal_done_{meta_id}",
            type="primary",
            use_container_width=True,
        ):
            self._concluir_meta(meta_id, titulo)
    
    def _concluir_meta(self, meta_id: str, titulo: str) -> None:
        """Conclui uma meta com tratamento de erros."""
        try:
            success = self.svc.concluir_meta(meta_id)
            
            if success:
                self._processar_sucesso_conclusao(titulo)
            else:
                st.error("❌ Erro ao concluir meta.")
        except Exception as e:
            logger.error(f"Erro ao concluir meta {meta_id}: {e}", exc_info=True)
            st.error(f"❌ Erro ao concluir meta: {str(e)}")
    
    def _processar_sucesso_conclusao(self, titulo: str) -> None:
        """Processa sucesso da conclusão de meta."""
        st.toast(f"🏆 Meta '{titulo}' concluída! +{self.XP_META_CONCLUIDA} XP", icon="🎉")
        xp_toast(self.XP_META_CONCLUIDA, "meta concluída")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def _render_meta_concluida(self, meta: Dict[str, Any]) -> None:
        """Renderiza uma meta concluída."""
        data_conclusao = self._formatar_data(meta.get("concluida_em"))
        titulo = meta.get("titulo", "Meta")
        tipo = meta.get("tipo", "livre")
        
        icone, _ = self._get_tipo_info(tipo)
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center;
                padding: 0.65rem 0.85rem; background: var(--success-bg);
                border: 1px solid var(--success); border-radius: 12px;
                margin-bottom: 0.5rem;">
                <span style="font-weight: 600; font-size: 0.9rem; color: var(--text);">
                    {icone} {titulo}
                </span>
                <span style="font-size: 0.78rem; color: var(--success);">
                    ✅ {data_conclusao}
                </span>
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


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = GoalsRenderer(services, user)
    renderer.render()
