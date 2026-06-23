"""
Melshape — Tela Pós-Bariátrica.

Para pacientes em acompanhamento após cirurgia bariátrica.
Fase atual calculada automaticamente por dias pós-cirurgia.
Suplementação obrigatória por fase. Alertas de volume e proteína.
"""
import streamlit as st
from typing import Dict, Any, Optional
from dataclasses import dataclass

from services.bariatric_service import BariatricService
from views.components.cards import (
    section_header, empty_state, metric_card, alert,
)
from views.patient.bariatric_tabs import _tab_suplementos, _tab_historico
from views.patient.bariatric_forms import (
    render_form_cirurgia, render_form_fase,
)
import config


@dataclass
class BariatricSummary:
    """Resumo do acompanhamento bariátrico."""
    fase: Dict[str, Any]
    fase_key: str
    progresso: Dict[str, Any]
    dias: Optional[int]
    tipo: str
    suplementos: list
    cirurgia: Optional[Dict]


class BariatricRenderer:
    """Renderer dedicado para tela pós-bariátrica."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.svc = BariatricService(self.db)
    
    def render(self) -> None:
        """Renderiza tela principal."""
        # Verifica se paciente tem cadastro bariátrico
        if not self.user.get("is_bariatric") and not self.db.get_cirurgia():
            self._render_cadastro()
            return
        
        section_header(
            "🔪 Acompanhamento Pós-Bariátrica",
            "Cada fase exige atenção diferente — vamos juntos",
        )
        
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
    
    def _get_summary(self) -> BariatricSummary:
        """Obtém resumo do acompanhamento."""
        raw = self.svc.resumo(self.user)
        return BariatricSummary(
            fase=raw.get("fase", {}),
            fase_key=raw.get("fase_key", "liquid"),
            progresso=raw.get("progresso", {"pct": 0}),
            dias=raw.get("dias"),
            tipo=raw.get("tipo", "—"),
            suplementos=raw.get("suplementos", []),
            cirurgia=raw.get("cirurgia"),
        )
    
    def _render_alertas(self, resumo: BariatricSummary) -> None:
        """Renderiza alertas clínicos."""
        for kind, msg in self.svc.alertas(resumo.fase_key, self.user):
            alert(msg, kind)
    
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
        fase = resumo.fase
        progresso = resumo.progresso
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(
                f"""
                <div class="metric-card fade-in">
                    <div style="font-size:0.76rem;color:var(--text-muted);">Fase atual</div>
                    <div style="font-weight:800;font-size:1.1rem;color:var(--primary);">
                        {fase.get("nome", "—")}
                    </div>
                    <div style="font-size:0.74rem;color:var(--text-muted);">
                        Dias {fase.get("dias", "—")} · Máx {fase.get("max_ml", "—")}ml · 
                        {fase.get("max_cal", "—")} kcal
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        
        with col2:
            dias_text = f"{resumo.dias}d" if resumo.dias is not None else "—"
            metric_card(dias_text, "Dias pós-cirurgia", "📅")
        
        with col3:
            pct = progresso.get("pct", 0)
            cor = "success" if pct >= 50 else ""
            metric_card(f"{pct}%", "Progresso (365d)", "🎯", cor)
        
        # Barra de progresso
        self._render_progress_bar(pct, resumo.dias)
        
        # Tipo de cirurgia
        st.markdown(
            f"""
            <div style="font-size:0.80rem;color:var(--text-muted);">
                Cirurgia: <b>{resumo.tipo}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_progress_bar(self, pct: int, dias: Optional[int]) -> None:
        """Renderiza barra de progresso."""
        st.markdown(
            f"""
            <div style="margin:0.6rem 0;">
                <div class="progress-track">
                    <div class="progress-fill" style="width:{pct}%;"></div>
                </div>
                <div class="progress-meta">
                    <span>{dias or 0} dias</span>
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
        fases_ordem = ["liquid", "pasty", "soft", "solid", "maintenance"]
        
        for fk in fases_ordem:
            fd = self.svc.fase_data(fk)
            atual = fk == fase_key
            passada = fases_ordem.index(fk) < fases_ordem.index(fase_key)
            
            cor = (
                "var(--primary)" if atual
                else "var(--success)" if passada
                else "var(--border)"
            )
            icon = "📍" if atual else "✅" if passada else "○"
            peso_txt = "font-weight:800;" if atual else ""
            
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:0.7rem;
                    padding:0.55rem 0.8rem;border:1px solid {cor};
                    border-radius:var(--radius-md);margin-bottom:0.4rem;
                    background:var(--surface);">
                    <span style="font-size:1.1rem;flex-shrink:0;">{icon}</span>
                    <div style="flex:1;">
                        <div style="{peso_txt}font-size:0.92rem;color:var(--text);">
                            {fd.get("nome", fk)}
                        </div>
                        <div style="font-size:0.74rem;color:var(--text-muted);">
                            Dias {fd.get("dias", "—")} · Máx {fd.get("max_ml", "—")}ml · {fd.get("max_cal", "—")} kcal
                        </div>
                    </div>
                    {"<span style=font-size:0.72rem;color:var(--primary);font-weight:700;>ATUAL</span>" if atual else ""}
                </div>
                """,
                unsafe_allow_html=True,
            )


# Interface compatível com o sistema existente
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = BariatricRenderer(services, user)
    renderer.render()
