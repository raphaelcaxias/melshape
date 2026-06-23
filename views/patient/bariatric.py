"""
Melshape — Tela Pós-Bariátrica.

Para pacientes em acompanhamento após cirurgia bariátrica.
Fase atual calculada automaticamente por dias pós-cirurgia.
Suplementação obrigatória por fase. Alertas de volume e proteína.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

from services.bariatric_service import BariatricService
from views.components.cards import (
    section_header, empty_state, metric_card, alert,
)
from views.patient.bariatric_tabs import _tab_suplementos, _tab_historico
from views.patient.bariatric_forms import (
    render_form_cirurgia, render_form_fase,
)
import config

logger = logging.getLogger("Melshape.Bariatric")


@dataclass
class BariatricSummary:
    """Resumo do acompanhamento bariátrico."""
    fase: Dict[str, Any] = field(default_factory=dict)
    fase_key: str = "liquid"
    progresso: Dict[str, Any] = field(default_factory=lambda: {"pct": 0})
    dias: Optional[int] = None
    tipo: str = "—"
    suplementos: List[Dict] = field(default_factory=list)
    cirurgia: Optional[Dict] = None


class BariatricRenderer:
    """Renderer dedicado para tela pós-bariátrica."""
    
    FASES_ORDEM = ["liquid", "pasty", "soft", "solid", "maintenance"]
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.svc = BariatricService(self.db)
        
        # Cache de dados para evitar múltiplas consultas
        self._resumo_cache: Optional[BariatricSummary] = None
    
    def render(self) -> None:
        """Renderiza tela principal."""
        # Verifica se paciente tem cadastro bariátrico
        if not self._has_bariatric_data():
            self._render_cadastro()
            return
        
        section_header(
            "🔪 Acompanhamento Pós-Bariátrica",
            "Cada fase exige atenção diferente — vamos juntos",
        )
        
        # Busca resumo UMA ÚNICA VEZ
        resumo = self._get_summary()
        
        # Alertas clínicos
        self._render_alertas(resumo)
        
        # Bloco de resumo
        self._render_resumo_bloco(resumo)
        
        st.divider()
        
        # Tabs
        tab_fase, tab_supl, tab_hist = st.tabs([
            "📋 Fase Atual",
            "💊 Suplementação",
            "📅 Histórico",
        ])
        
        with tab_fase:
            self._render_tab_fase(resumo)
        
        with tab_supl:
            _tab_suplementos(resumo)
        
        with tab_hist:
            _tab_historico(self.db, resumo)
    
    def _has_bariatric_data(self) -> bool:
        """Verifica se o usuário tem dados bariátricos cadastrados."""
        if self.user.get("is_bariatric"):
            return True
        
        try:
            return bool(self.db.get_cirurgia())
        except Exception as e:
            logger.debug(f"Erro ao verificar cadastro bariátrico: {e}")
            return False
    
    @st.cache_data(ttl=60)
    def _get_summary(_self) -> BariatricSummary:
        """Obtém resumo do acompanhamento (com cache)."""
        try:
            raw = _self.svc.resumo(_self.user)
            return BariatricSummary(
                fase=raw.get("fase", {}),
                fase_key=raw.get("fase_key", "liquid"),
                progresso=raw.get("progresso", {"pct": 0}),
                dias=raw.get("dias"),
                tipo=raw.get("tipo", "—"),
                suplementos=raw.get("suplementos", []),
                cirurgia=raw.get("cirurgia"),
            )
        except Exception as e:
            logger.error(f"Erro ao obter resumo bariátrico: {e}", exc_info=True)
            return BariatricSummary()
    
    def _render_alertas(self, resumo: BariatricSummary) -> None:
        """Renderiza alertas clínicos."""
        try:
            alertas = self.svc.alertas(resumo.fase_key, self.user)
            for kind, msg in alertas:
                alert(msg, kind)
        except Exception as e:
            logger.error(f"Erro ao renderizar alertas: {e}", exc_info=True)
    
    def _render_cadastro(self) -> None:
        """Renderiza tela de cadastro inicial."""
        section_header(
            "🔪 Pós-Bariátrica",
            "Registre sua cirurgia para começar o acompanhamento",
        )
        alert(
            "Você ainda não cadastrou sua cirurgia. "
            "Preencha os dados abaixo para ativar o módulo bariátrico.",
            "info",
        )
        render_form_cirurgia(self.db, self.svc, self.user)
    
    def _render_resumo_bloco(self, resumo: BariatricSummary) -> None:
        """Renderiza bloco de resumo."""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self._render_card_fase_atual(resumo)
        
        with col2:
            dias_text = f"{resumo.dias}d" if resumo.dias is not None else "—"
            metric_card(dias_text, "Dias pós-cirurgia", "📅")
        
        with col3:
            pct = self._parse_pct(resumo.progresso)
            cor = "success" if pct >= 50 else ""
            metric_card(f"{pct}%", "Progresso (365d)", "🎯", cor)
        
        # Barra de progresso
        pct = self._parse_pct(resumo.progresso)
        self._render_progress_bar(pct, resumo.dias)
        
        # Tipo de cirurgia
        st.markdown(
            f"""
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.5rem;">
                Cirurgia: <b>{resumo.tipo}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _parse_pct(self, progresso: Dict[str, Any]) -> int:
        """Extrai percentual de progresso de forma segura."""
        try:
            pct = int(progresso.get("pct", 0))
            return min(max(pct, 0), 100)  # Garante entre 0 e 100
        except (ValueError, TypeError):
            return 0
    
    def _render_card_fase_atual(self, resumo: BariatricSummary) -> None:
        """Renderiza card da fase atual."""
        fase = resumo.fase
        nome = fase.get("nome", "—")
        dias = fase.get("dias", "—")
        max_ml = fase.get("max_ml", "—")
        max_cal = fase.get("max_cal", "—")
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="font-size: 0.76rem; color: var(--text-muted);">Fase atual</div>
                <div style="font-weight: 800; font-size: 1.1rem; color: var(--primary);">
                    {nome}
                </div>
                <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 0.2rem;">
                    Dias {dias} · Máx {max_ml}ml · {max_cal} kcal
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_progress_bar(self, pct: int, dias: Optional[int]) -> None:
        """Renderiza barra de progresso."""
        dias_text = dias or 0
        
        st.markdown(
            f"""
            <div style="margin: 0.8rem 0;">
                <div style="background: var(--surface-2); border-radius: 8px; 
                    height: 10px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, #10b981, #34d399); 
                        height: 100%; width: {pct}%; border-radius: 8px; 
                        transition: width 0.5s ease;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; 
                    font-size: 0.72rem; color: var(--text-faint); margin-top: 0.3rem;">
                    <span>{dias_text} dias</span>
                    <span>{pct}%</span>
                    <span>Meta: 365 dias</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_tab_fase(self, resumo: BariatricSummary) -> None:
        """Renderiza aba de fase atual."""
        fase_key = resumo.fase_key
        
        # Linha do tempo de todas as fases
        self._render_fases_timeline(fase_key)
        
        st.markdown("---")
        st.markdown("**Atualizar fase manualmente:**")
        render_form_fase(self.db, self.svc, resumo.__dict__)
    
    def _render_fases_timeline(self, fase_key: str) -> None:
        """Renderiza linha do tempo das fases."""
        try:
            fase_atual_idx = self.FASES_ORDEM.index(fase_key)
        except ValueError:
            fase_atual_idx = 0
            logger.warning(f"Fase '{fase_key}' não encontrada na lista")
        
        for idx, fk in enumerate(self.FASES_ORDEM):
            fd = self._get_fase_data(fk)
            atual = fk == fase_key
            passada = idx < fase_atual_idx
            
            self._render_fase_item(fd, fk, atual, passada)
    
    def _get_fase_data(self, fase_key: str) -> Dict[str, Any]:
        """Obtém dados da fase com fallback."""
        try:
            return self.svc.fase_data(fase_key)
        except Exception as e:
            logger.warning(f"Erro ao obter dados da fase '{fase_key}': {e}")
            return {"nome": fase_key, "dias": "—", "max_ml": "—", "max_cal": "—"}
    
    def _render_fase_item(
        self,
        fd: Dict[str, Any],
        fase_key: str,
        atual: bool,
        passada: bool,
    ) -> None:
        """Renderiza item individual da timeline de fases."""
        cor = self._get_fase_cor(atual, passada)
        icon = "📍" if atual else "✅" if passada else "○"
        peso_txt = "font-weight: 800;" if atual else ""
        
        nome = fd.get("nome", fase_key)
        dias = fd.get("dias", "—")
        max_ml = fd.get("max_ml", "—")
        max_cal = fd.get("max_cal", "—")
        
        badge_atual = (
            '<span style="font-size: 0.72rem; color: var(--primary); '
            'font-weight: 700; margin-left: auto;">ATUAL</span>'
            if atual else ""
        )
        
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 0.7rem;
                padding: 0.6rem 0.85rem; border: 1px solid {cor};
                border-radius: 12px; margin-bottom: 0.5rem;
                background: var(--surface);">
                <span style="font-size: 1.2rem; flex-shrink: 0;">{icon}</span>
                <div style="flex: 1;">
                    <div style="{peso_txt} font-size: 0.92rem; color: var(--text);">
                        {nome}
                    </div>
                    <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 0.15rem;">
                        Dias {dias} · Máx {max_ml}ml · {max_cal} kcal
                    </div>
                </div>
                {badge_atual}
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_fase_cor(self, atual: bool, passada: bool) -> str:
        """Retorna cor da borda baseada no status da fase."""
        if atual:
            return "var(--primary)"
        elif passada:
            return "var(--success)"
        else:
            return "var(--border)"


# Interface compatível com o sistema existente
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = BariatricRenderer(services, user)
    renderer.render()
