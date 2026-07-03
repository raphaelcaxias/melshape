"""
Melshape — Evolução: aba Corpo (medidas corporais e fotos).

Importado por complete_evolution.py:
    from views.patient.evolution_corpo import _tab_corpo

Campos alinhados com a tabela real ``medidas_corporais`` do Supabase,
conforme mapeado em EvolutionService.salvar_medida():
    peso, cintura, quadril, braco, coxa, gordura
"""
from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from services.evolution_service import EvolutionService
from views.components.cards import empty_state

logger = logging.getLogger("Melshape.EvolutionCorpo")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

_CACHE_TTL = 60
_DEFAULT_DAYS = 90
_MAX_HISTORICO = 5


# ─────────────────────────────────────────────────────────────────────────────
# ABA CORPO
# ─────────────────────────────────────────────────────────────────────────────

def _tab_corpo(svc: EvolutionService, user: dict[str, Any]) -> None:
    """Renderiza aba de medidas corporais.

    Args:
        svc:  Instância do EvolutionService.
        user: Dados do usuário logado.
    """
    st.markdown("##### 📏 Medidas Corporais")

    # ── Formulário de registro ─────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        peso = st.number_input(
            "Peso (kg)", min_value=30.0, max_value=300.0,
            value=float(user.get("current_weight", 70.0)),
            step=0.1, key="ev_peso",
        )
        cintura = st.number_input(
            "Cintura (cm)", min_value=50.0, max_value=200.0,
            value=80.0, step=0.5, key="ev_cintura",
        )

    with col2:
        quadril = st.number_input(
            "Quadril (cm)", min_value=50.0, max_value=200.0,
            value=95.0, step=0.5, key="ev_quadril",
        )
        braco = st.number_input(
            "Braço (cm)", min_value=20.0, max_value=60.0,
            value=30.0, step=0.5, key="ev_braco",
        )

    with col3:
        coxa = st.number_input(
            "Coxa (cm)", min_value=30.0, max_value=80.0,
            value=50.0, step=0.5, key="ev_coxa",
        )
        gordura = st.number_input(
            "% Gordura", min_value=5.0, max_value=60.0,
            value=25.0, step=0.5, key="ev_gordura",
        )

    if st.button(
        "📏 Salvar medidas",
        type="primary",
        use_container_width=True,
        key="ev_save_medidas",
    ):
        dados = {
            "peso": peso,
            "cintura": cintura,
            "quadril": quadril,
            "braco": braco,
            "coxa": coxa,
            "gordura": gordura,
        }
        if svc.salvar_medida(dados):
            st.toast("📏 Medidas salvas!", icon="✅")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("❌ Erro ao salvar medidas.")

    # ── Histórico ──────────────────────────────────────────────────────────
    st.markdown("---")
    medidas = _get_medidas(svc)

    if not medidas:
        empty_state(
            "📏",
            "Nenhuma medida registrada",
            "Registre suas medidas para acompanhar a evolução.",
        )
        return

    st.markdown(
        f'<div style="font-size: 0.85rem; color: var(--text-muted); '
        f'margin-bottom: 0.6rem;">📅 Últimas <b>{len(medidas)}</b> medidas</div>',
        unsafe_allow_html=True,
    )

    for m in medidas[:_MAX_HISTORICO]:
        m_dict = m.to_dict() if hasattr(m, "to_dict") else m
        data = m_dict.get("data_medicao", "")[:10]
        peso_val = m_dict.get("peso", "—")
        cintura_val = m_dict.get("circunferencia_cintura", m_dict.get("cintura", "—"))
        gordura_val = m_dict.get("percentual_gordura", m_dict.get("gordura", "—"))

        st.markdown(
            f"""
            <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle);">
                <div style="font-weight: 600; font-size: 0.88rem; color: var(--text);">{data}</div>
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">
                    Peso: {peso_val}kg
                    · Cintura: {cintura_val}cm
                    · Gordura: {gordura_val}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=_CACHE_TTL)
def _get_medidas(svc: EvolutionService) -> list:
    """Obtém medidas corporais (com cache).

    Args:
        svc: Instância do EvolutionService.

    Returns:
        Lista de MedidaCorporal ou dicts.
    """
    try:
        return svc.get_medidas(days=_DEFAULT_DAYS) or []
    except Exception as e:
        logger.error(f"_get_medidas: {e}")
        return []
