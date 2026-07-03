"""
Melshape — Tela GLP-1.

Para pacientes usando Ozempic, Wegovy, Mounjaro, Saxenda etc.
Registro de dose, monitoramento de sintomas, adesão e evolução.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

from services.glp1_service import GLP1Service
from views.components.cards import (
    section_header, empty_state, metric_card, alert,
    xp_toast, show_new_achievements,
)
from views.patient.glp1_forms import render_form_dose, render_form_sintomas
import config

logger = logging.getLogger("Melshape.GLP1")


@dataclass
class GLP1Resumo:
    """Resumo do acompanhamento GLP-1."""
    fase: Dict[str, Any] = field(default_factory=lambda: {
        "icon": "💉",
        "label": "Adaptação",
        "desc": "Início do tratamento"
    })
    dias: Optional[int] = None
    adesao: Dict[str, Any] = field(default_factory=lambda: {"pct": 0})
    medicamento: str = "—"
    dose_atual: str = "—"
    proxima_dose: str = "—"


class GLP1Renderer:
    """Renderer dedicado para tela GLP-1."""
    
    # Constantes de fases GLP-1
    FASES_GLP1 = {
        "adapting": "🔬 Adaptação",
        "maintenance": "✅ Manutenção",
        "tapering": "📉 Desmame",
        "stopped": "⏹️ Parado",
    }
    
    # Constantes de limiares de adesão
    ADESAO_EXCELENTE = 80
    ADESAO_BOM = 50
    
    # Constantes de limites
    MAX_DOSES_HISTORICO = 90
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.gami = services.get("gamification")
        self.svc = self._init_glp1_service()
    
    def _init_glp1_service(self) -> Optional[GLP1Service]:
        """Inicializa GLP1Service com tratamento de erros."""
        if not self.db:
            logger.error("Database não disponível para GLP1Renderer")
            return None
        
        try:
            return GLP1Service(self.db)
        except Exception as e:
            logger.error(f"Erro ao inicializar GLP1Service: {e}", exc_info=True)
            return None
    
    def render(self) -> None:
        """Renderiza tela GLP-1."""
        # Valida pilar
        if not self._is_glp1_user():
            self._render_nao_glp1()
            return
        
        # Verifica se serviço foi inicializado
        if not self.svc:
            self._render_error_state()
            return
        
        section_header("💉 Acompanhamento GLP-1", "Monitore seu tratamento e evolução")
        
        # Busca resumo UMA ÚNICA VEZ
        resumo = self._get_resumo()
        
        # Bloco de resumo
        self._render_resumo_bloco(resumo)
        
        # Alertas de sintomas graves
        self._render_alertas_sintomas()
        
        st.divider()
        
        # Tabs
        self._render_tabs(resumo)
    
    def _is_glp1_user(self) -> bool:
        """Verifica se usuário é paciente GLP-1."""
        try:
            return (
                self.user.get("health_mode") == "glp1" or
                self.user.get("uses_glp1", False)
            )
        except Exception as e:
            logger.debug(f"Erro ao verificar se é usuário GLP-1: {e}")
            return False
    
    def _render_error_state(self) -> None:
        """Renderiza estado de erro quando serviço não está disponível."""
        alert(
            "❌ Não foi possível carregar o módulo GLP-1. "
            "Por favor, recarregue a página ou entre em contato com o suporte.",
            "error",
        )
    
    @st.cache_data(ttl=60)
    def _get_resumo(_self) -> GLP1Resumo:
        """Obtém resumo do acompanhamento (com cache)."""
        try:
            raw = _self.svc.resumo(_self.user)
            
            return GLP1Resumo(
                fase=raw.get("fase", {
                    "icon": "💉",
                    "label": "Adaptação",
                    "desc": "Início do tratamento"
                }),
                dias=raw.get("dias"),
                adesao=raw.get("adesao", {"pct": 0}),
                medicamento=raw.get("medicamento") or "—",
                dose_atual=raw.get("dose_atual") or "—",
                proxima_dose=raw.get("proxima_dose") or "—",
            )
        except Exception as e:
            logger.error(f"Erro ao obter resumo GLP-1: {e}", exc_info=True)
            return GLP1Resumo()
    
    def _render_resumo_bloco(self, resumo: GLP1Resumo) -> None:
        """Renderiza bloco de resumo."""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            self._render_card_fase(resumo)
        
        with col2:
            dias_text = f"{resumo.dias}d" if resumo.dias is not None else "—"
            metric_card(dias_text, "Dias de tratamento", "📅")
        
        with col3:
            self._render_card_adesao(resumo)
        
        with col4:
            self._render_card_medicamento(resumo)
    
    def _render_card_fase(self, resumo: GLP1Resumo) -> None:
        """Renderiza card da fase atual."""
        fase = resumo.fase
        icon = fase.get("icon", "💉")
        label = fase.get("label", "—")
        desc = fase.get("desc", "")
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="font-size: 1.5rem; margin-bottom: 0.2rem;">{icon}</div>
                <div style="font-weight: 700; font-size: 0.94rem; color: var(--text);">
                    {label}
                </div>
                <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.2rem;">
                    {desc}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_card_adesao(self, resumo: GLP1Resumo) -> None:
        """Renderiza card de adesão."""
        pct = self._parse_adesao_pct(resumo.adesao)
        cor = self._get_cor_adesao(pct)
        metric_card(f"{pct}%", "Adesão (4 sem.)", "✅", cor)
    
    def _parse_adesao_pct(self, adesao: Dict[str, Any]) -> int:
        """Parse percentual de adesão de forma segura."""
        try:
            pct = int(adesao.get("pct", 0))
            return min(max(pct, 0), 100)  # Garante entre 0 e 100
        except (ValueError, TypeError):
            return 0
    
    def _get_cor_adesao(self, pct: int) -> str:
        """Retorna cor baseada no percentual de adesão."""
        if pct >= self.ADESAO_EXCELENTE:
            return "success"
        elif pct >= self.ADESAO_BOM:
            return "warning"
        else:
            return "error"
    
    def _render_card_medicamento(self, resumo: GLP1Resumo) -> None:
        """Renderiza card do medicamento."""
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="font-size: 0.78rem; color: var(--text-muted);">
                    Medicamento
                </div>
                <div style="font-weight: 700; font-size: 0.90rem; color: var(--text); margin-top: 0.2rem;">
                    {resumo.medicamento}
                </div>
                <div style="font-size: 0.78rem; color: var(--primary); margin-top: 0.2rem;">
                    Dose: {resumo.dose_atual}
                </div>
                <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem;">
                    Próxima: {resumo.proxima_dose}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_alertas_sintomas(self) -> None:
        """Renderiza alertas de sintomas graves."""
        alertas = self._get_alertas_sintomas()
        
        if not alertas:
            return
        
        for alerta in alertas:
            tipo = "error" if "⚠️" in alerta else "warning"
            alert(alerta, tipo)
    
    @st.cache_data(ttl=30)
    def _get_alertas_sintomas(_self) -> List[str]:
        """Obtém alertas de sintomas (com cache)."""
        try:
            alertas = _self.svc.alertas_sintomas()
            return alertas if isinstance(alertas, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar alertas de sintomas: {e}", exc_info=True)
            return []
    
    def _render_tabs(self, resumo: GLP1Resumo) -> None:
        """Renderiza as 3 tabs de GLP-1."""
        tab_dose, tab_sintomas, tab_historico = st.tabs([
            "💉 Registrar Dose",
            "📋 Sintomas",
            "📈 Histórico",
        ])
        
        with tab_dose:
            self._render_tab_dose(resumo)
        
        with tab_sintomas:
            self._render_tab_sintomas()
        
        with tab_historico:
            self._render_historico()
    
    def _render_tab_dose(self, resumo: GLP1Resumo) -> None:
        """Renderiza tab de registro de dose com tratamento de erros."""
        try:
            render_form_dose(self.db, self.svc, self.gami, self.user, resumo.__dict__)
        except Exception as e:
            logger.error(f"Erro ao renderizar formulário de dose: {e}", exc_info=True)
            alert("❌ Erro ao carregar formulário de dose.", "error")
    
    def _render_tab_sintomas(self) -> None:
        """Renderiza tab de sintomas com tratamento de erros."""
        try:
            render_form_sintomas(self.db, self.svc, self.gami, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar formulário de sintomas: {e}", exc_info=True)
            alert("❌ Erro ao carregar formulário de sintomas.", "error")
    
    def _render_historico(self) -> None:
        """Renderiza histórico de doses."""
        doses = self._get_doses()
        
        if not doses:
            empty_state(
                "💉",
                "Nenhuma dose registrada",
                "Registre sua primeira dose na aba 'Registrar Dose'",
            )
            return
        
        self._render_historico_header(len(doses))
        
        for dose in doses:
            self._render_dose_item(dose)
    
    @st.cache_data(ttl=60)
    def _get_doses(_self) -> List[Dict]:
        """Obtém histórico de doses (com cache)."""
        try:
            doses = _self.db.get_doses_glp1(days=_self.MAX_DOSES_HISTORICO)
            return doses or []
        except Exception as e:
            logger.error(f"Erro ao buscar doses GLP-1: {e}", exc_info=True)
            return []
    
    def _render_historico_header(self, total: int) -> None:
        """Renderiza cabeçalho do histórico."""
        st.markdown(
            f"""
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.8rem;">
                <b>{total}</b> dose(s) nos últimos {self.MAX_DOSES_HISTORICO} dias
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_dose_item(self, dose: Dict[str, Any]) -> None:
        """Renderiza um item do histórico de doses."""
        data = self._formatar_data(dose.get("data_aplicacao"))
        medicamento = dose.get("medicamento", "—")
        dose_valor = dose.get("dose", "—")
        fase = dose.get("fase", "")
        observacao = dose.get("observacao", "")
        
        fase_label = self.FASES_GLP1.get(fase, fase)
        obs_texto = f"  ·  {observacao}" if observacao else ""
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between;
                align-items: flex-start; padding: 0.65rem 0.85rem;
                border: 1px solid var(--border); border-radius: 12px;
                margin-bottom: 0.5rem; background: var(--surface);">
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 0.92rem; color: var(--text);">
                        💉 {dose_valor} — {medicamento}
                    </div>
                    <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">
                        {fase_label}{obs_texto}
                    </div>
                </div>
                <div style="font-size: 0.80rem; color: var(--text-faint); margin-left: 1rem;">
                    {data}
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
    
    def _render_nao_glp1(self) -> None:
        """Renderiza tela para pacientes não GLP-1."""
        section_header("💉 GLP-1", "Acompanhamento de medicamentos")
        alert(
            "Esta seção é para pacientes usando medicamentos GLP-1 "
            "(Ozempic, Wegovy, Mounjaro, Saxenda). "
            "Atualize seu perfil para ativar este módulo.",
            "info",
        )
        
        if st.button(
            "Ir para o Perfil →",
            use_container_width=True,
            key="glp1_go_profile",
        ):
            st.session_state.page = "profile"
            st.rerun()


# Função de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = GLP1Renderer(services, user)
    renderer.render()
