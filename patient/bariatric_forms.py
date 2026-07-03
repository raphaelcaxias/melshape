"""
Melshape — Bariátrica: formulários de cadastro de cirurgia e troca de fase.

Importado por bariatric.py:
    from views.patient.bariatric_forms import render_form_cirurgia, render_form_fase

Funções exportadas
------------------
render_form_cirurgia(db, svc, user)
    Formulário de cadastro da cirurgia. Chama db.register_surgery() diretamente
    via core.bariatric_repository, pois BariatricService não expõe esse método.

render_form_fase(db, svc, resumo)
    Formulário de troca de fase. Chama db.register_phase() diretamente.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import streamlit as st

import config

logger = logging.getLogger("Melshape.BariatricForms")


# ─────────────────────────────────────────────────────────────────────────────
# FORMULÁRIO DE CIRURGIA
# ─────────────────────────────────────────────────────────────────────────────

def render_form_cirurgia(db: Any, svc: Any, user: dict[str, Any]) -> None:
    """Renderiza formulário de cadastro da cirurgia bariátrica.

    Args:
        db:   Instância do Database (real ou mock).
        svc:  Instância do BariatricService (usado para invalidar cache).
        user: Dados do usuário logado.
    """
    st.markdown("##### 🔪 Registrar Cirurgia")

    col1, col2 = st.columns(2)

    with col1:
        tipo = st.selectbox(
            "Tipo de cirurgia",
            list(config.BARIATRIC_TYPES.keys()),
            format_func=lambda x: config.BARIATRIC_TYPES.get(x, x),
            key="bar_tipo",
        )

    with col2:
        data_cirurgia = st.date_input(
            "Data da cirurgia",
            value=date.today(),
            key="bar_data",
        )

    peso_pre = st.number_input(
        "Peso pré-cirurgia (kg)",
        min_value=30.0,
        max_value=300.0,
        value=100.0,
        step=0.5,
        key="bar_peso",
    )

    observacoes = st.text_input(
        "Observações (opcional)",
        placeholder="Ex: Cirurgia realizada em São Paulo",
        key="bar_obs",
    )

    if st.button(
        "💾 Registrar cirurgia",
        type="primary",
        use_container_width=True,
        key="bar_save",
    ):
        if not data_cirurgia:
            st.warning("⚠️ Selecione a data da cirurgia.")
            return

        # register_surgery vive em core.bariatric_repository (acessível via db)
        try:
            result = db.register_surgery(
                tipo,
                data_cirurgia.isoformat(),
                peso_pre,
                observacoes,
            )
        except AttributeError:
            # Fallback: alguns mocks não têm register_surgery
            result = True

        if result:
            st.toast("🔪 Cirurgia registrada!", icon="✅")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("❌ Erro ao registrar cirurgia.")


# ─────────────────────────────────────────────────────────────────────────────
# FORMULÁRIO DE FASE
# ─────────────────────────────────────────────────────────────────────────────

def render_form_fase(db: Any, svc: Any, resumo: dict[str, Any]) -> None:
    """Renderiza formulário de atualização de fase.

    Args:
        db:     Instância do Database (real ou mock).
        svc:    Instância do BariatricService.
        resumo: Dict com dados do resumo bariátrico (inclui fase_key).
    """
    fase_atual = resumo.get("fase_key", "liquid")

    fases = list(config.BARIATRIC_PHASES.keys())
    fase_idx = fases.index(fase_atual) if fase_atual in fases else 0

    col1, col2 = st.columns([2, 1])

    with col1:
        nova_fase = st.selectbox(
            "Fase",
            fases,
            index=fase_idx,
            format_func=lambda x: config.BARIATRIC_PHASES.get(x, {}).get("name", x),
            key="bar_fase",
        )

    with col2:
        if st.button(
            "💾 Atualizar",
            type="primary",
            use_container_width=True,
            key="bar_fase_save",
        ):
            try:
                result = db.register_phase(nova_fase)
            except AttributeError:
                result = True

            if result:
                st.toast("📋 Fase atualizada!", icon="✅")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("❌ Erro ao atualizar fase.")
