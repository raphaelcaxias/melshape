"""
Melshape — Bariátrica: tabs de suplementação e histórico.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from datetime import date
import logging

from views.components.cards import empty_state, alert
import config

logger = logging.getLogger("Melshape.BariatricTabs")


class BariatricTabsRenderer:
    """Renderer dedicado para as tabs bariátricas."""
    
    def __init__(self, db):
        self.db = db
    
    def render_suplementos(self, resumo: Dict[str, Any]) -> None:
        """Renderiza aba de suplementação."""
        suplementos = resumo.get("suplementos", [])
        fase_nome = resumo.get("fase", {}).get("nome", "—")
        
        self._render_suplementos_header(fase_nome)
        
        if not suplementos:
            empty_state("💊", "Sem suplementos para esta fase")
            return
        
        for suplemento in suplementos:
            self._render_suplemento_item(suplemento)
        
        self._render_aviso_medico()
    
    def _render_suplementos_header(self, fase_nome: str) -> None:
        """Renderiza cabeçalho da aba de suplementos."""
        st.markdown(
            f"""
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                💊 Suplementação obrigatória — fase <b>{fase_nome}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_aviso_medico(self) -> None:
        """Renderiza aviso médico sobre suplementação."""
        alert(
            "⚕️ Suplementação conforme orientação médica. "
            "Doses podem variar por prescrição individual.",
            "info",
        )
    
    def _render_suplemento_item(self, suplemento: Dict[str, Any]) -> None:
        """Renderiza um item de suplemento."""
        nome = suplemento.get("name", "Suplemento")
        dose_str = self._formatar_dose(suplemento)
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center;
                padding: 0.6rem 0.85rem; border: 1px solid var(--border);
                border-radius: 12px; margin-bottom: 0.4rem; background: var(--surface);">
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 0.9rem; color: var(--text);">
                        💊 {nome}
                    </div>
                </div>
                <span style="font-size: 0.82rem; color: var(--primary);
                    font-weight: 600; margin-left: 1rem;">{dose_str}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _formatar_dose(self, suplemento: Dict[str, Any]) -> str:
        """Formata dose do suplemento de forma segura."""
        dose = suplemento.get("dose", "—")
        unit = suplemento.get("unit", "")
        
        if dose == "—" or not dose:
            return "—"
        
        dose_str = str(dose).strip()
        unit_str = str(unit).strip() if unit else ""
        
        return f"{dose_str} {unit_str}".strip()
    
    def render_historico(self, resumo: Dict[str, Any]) -> None:
        """Renderiza aba de histórico de fases."""
        cirurgia = resumo.get("cirurgia")
        
        if cirurgia:
            self._render_cirurgia_info(cirurgia, resumo)
        
        historico = self._buscar_historico()
        
        if not historico:
            empty_state("📅", "Sem histórico de fases", "Suas mudanças de fase aparecerão aqui.")
            return
        
        self._render_historico_header(len(historico))
        
        for item in historico:
            self._render_historico_item(item)
    
    @st.cache_data(ttl=60)
    def _buscar_historico(_self) -> List[Dict]:
        """Busca histórico de fases do banco (com cache)."""
        if not _self.db:
            return []
        
        try:
            historico = _self.db.get_historico_fases()
            return historico or []
        except Exception as e:
            logger.error(f"Erro ao buscar histórico de fases: {e}", exc_info=True)
            return []
    
    def _render_historico_header(self, total: int) -> None:
        """Renderiza cabeçalho do histórico."""
        st.markdown(
            f"""
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.6rem;">
                📅 <b>{total}</b> fase(s) registrada(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_cirurgia_info(self, cirurgia: Dict, resumo: Dict) -> None:
        """Renderiza informações da cirurgia."""
        tipo = resumo.get("tipo", "—")
        data_cirurgia = self._formatar_data(cirurgia.get("data_cirurgia"))
        peso_pre = self._formatar_peso(cirurgia.get("peso_pre_cirurgia"))
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom: 1rem;">
                <div style="font-weight: 700; font-size: 0.95rem; color: var(--text);">
                    🔪 Cirurgia: {tipo}
                </div>
                <div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.3rem;">
                    Data: {data_cirurgia} · Peso pré: {peso_pre} kg
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
            # Tenta parsear para validar formato
            if len(data_str) == 10 and data_str[4] == "-" and data_str[7] == "-":
                # Formato YYYY-MM-DD, converte para DD/MM/YYYY
                ano, mes, dia = data_str.split("-")
                return f"{dia}/{mes}/{ano}"
            return data_str
        except Exception as e:
            logger.debug(f"Erro ao formatar data '{data_raw}': {e}")
            return str(data_raw)[:10] if data_raw else "—"
    
    def _formatar_peso(self, peso_raw: Any) -> str:
        """Formata peso de forma segura."""
        if not peso_raw:
            return "—"
        
        try:
            peso = float(peso_raw)
            return f"{peso:.1f}".replace(".", ",")
        except (ValueError, TypeError):
            return str(peso_raw)
    
    def _render_historico_item(self, item: Dict[str, Any]) -> None:
        """Renderiza um item do histórico."""
        fase_key = item.get("fase", "")
        nome = self._get_nome_fase(fase_key)
        data = self._formatar_data(item.get("iniciada_em"))
        obs = item.get("observacao", "")
        
        obs_html = (
            f'<div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.2rem;">'
            f'{obs}</div>'
            if obs else ""
        )
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: flex-start;
                padding: 0.6rem 0; border-bottom: 1px solid var(--border-subtle);">
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 0.88rem; color: var(--text);">
                        {nome}
                    </div>
                    {obs_html}
                </div>
                <span style="font-size: 0.76rem; color: var(--text-faint); margin-left: 1rem;">
                    {data}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_nome_fase(self, fase_key: str) -> str:
        """Obtém nome da fase do config com fallback."""
        try:
            return config.BARIATRIC_PHASES.get(fase_key, {}).get("name", fase_key)
        except Exception as e:
            logger.debug(f"Erro ao obter nome da fase '{fase_key}': {e}")
            return fase_key


# Funções de compatibilidade
def _tab_suplementos(resumo: Dict[str, Any]) -> None:
    """Renderiza tab de suplementos (compatibilidade)."""
    renderer = BariatricTabsRenderer(None)
    renderer.render_suplementos(resumo)


def _tab_historico(db, resumo: Dict[str, Any]) -> None:
    """Renderiza tab de histórico (compatibilidade)."""
    renderer = BariatricTabsRenderer(db)
    renderer.render_historico(resumo)
