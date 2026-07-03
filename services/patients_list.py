"""
Melshape — Lista de Pacientes com Busca e Filtro.

Auditoria Mestra (Auditoria 6): "Com 100 pacientes, o profissional
rola uma lista sem poder filtrar."

Reaproveita ProfessionalService.get_patients() — já existente,
nunca exposto numa view com busca/filtro reais.

Constituição:
- Cap. IV: o profissional precisa tomar decisões claras, não rolar listas
- Cap. VI: Uma Única Ação Principal — aqui, encontrar o paciente certo rápido
"""
from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from services.professional_service import ProfessionalService
from views.components.cards import empty_state, section_header

logger = logging.getLogger("Melshape.PatientsList")

_PILAR_LABELS = {
    "general":   "⚖️ Emagrecimento",
    "fitness":   "💪 Fitness",
    "bariatric": "🔪 Pós-Bariátrica",
    "glp1":      "💉 GLP-1",
}

_MAX_PACIENTES = 200


class PatientsListRenderer:
    def __init__(self, services: dict[str, Any], professional: Any) -> None:
        self.services = services
        self.db = services.get("db")
        self.svc = ProfessionalService(self.db)
        self.professional = professional
        self.pro_email = (
            professional.email if hasattr(professional, "email")
            else professional.get("email", "")
        )

    def render(self) -> None:
        section_header("👥 Meus Pacientes", "Busque, filtre e acesse rapidamente")

        pacientes = self._get_pacientes()
        if not pacientes:
            self._render_sem_pacientes()
            return

        # ── Busca + filtros ──────────────────────────────────────────────────
        col1, col2 = st.columns([3, 2])
        with col1:
            termo = st.text_input(
                "Buscar paciente",
                placeholder="Digite o nome...",
                key="pl_busca",
                label_visibility="collapsed",
            )
        with col2:
            pilares_disponiveis = ["Todos"] + sorted(
                {p.tipo_jornada for p in pacientes if getattr(p, "tipo_jornada", None)}
            )
            pilar_filtro = st.selectbox(
                "Pilar",
                pilares_disponiveis,
                format_func=lambda x: x if x == "Todos" else _PILAR_LABELS.get(x, x),
                key="pl_pilar",
                label_visibility="collapsed",
            )

        # ── Aplica filtros ───────────────────────────────────────────────────
        filtrados = pacientes
        if termo:
            termo_lower = termo.lower().strip()
            filtrados = [p for p in filtrados if termo_lower in p.nome_completo.lower()]
        if pilar_filtro != "Todos":
            filtrados = [p for p in filtrados if getattr(p, "tipo_jornada", None) == pilar_filtro]

        st.markdown(
            f'<div style="font-size:0.82rem;color:var(--text-muted);'
            f'margin:0.6rem 0;">{len(filtrados)} de {len(pacientes)} paciente(s)</div>',
            unsafe_allow_html=True,
        )

        if not filtrados:
            empty_state("🔍", "Nenhum paciente encontrado",
                       "Tente buscar com outro termo ou remova o filtro.")
            return

        # ── Lista ────────────────────────────────────────────────────────────
        for p in filtrados:
            self._render_paciente_item(p)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @st.cache_data(ttl=60)
    def _get_pacientes(_self) -> list:
        try:
            return _self.svc.get_patients(_self.pro_email, limit=_MAX_PACIENTES)
        except Exception as e:
            logger.error(f"_get_pacientes: {e}")
            return []

    def _render_sem_pacientes(self) -> None:
        empty_state(
            "👥",
            "Você ainda não tem pacientes vinculados",
            "Gere um link de convite e comece a acompanhar seus pacientes.",
        )
        if st.button("🔗 Convidar primeiro paciente →", type="primary",
                     use_container_width=True, key="pl_convite_cta"):
            st.session_state.page = "pro_convite"
            st.rerun()

    def _render_paciente_item(self, p: Any) -> None:
        nome = getattr(p, "nome_completo", "—")
        pilar = getattr(p, "tipo_jornada", "general")
        pilar_label = _PILAR_LABELS.get(pilar, pilar)
        peso = getattr(p, "peso_atual", None)
        peso_str = f"{peso:.1f}kg" if peso else "—"

        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        with col1:
            st.markdown(
                f'<div style="font-weight:600;font-size:0.92rem;'
                f'color:var(--text);padding:0.4rem 0;">{nome}</div>',
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f'<div style="font-size:0.78rem;color:var(--text-muted);'
                f'padding:0.4rem 0;">{pilar_label} · {peso_str}</div>',
                unsafe_allow_html=True,
            )
        with col3:
            if st.button("📄", key=f"pl_resumo_{nome}", help="Resumo pré-consulta",
                         use_container_width=True):
                st.session_state["pro_selected_patient"] = nome
                st.session_state.page = "pro_patient_detail"
                st.rerun()
        with col4:
            if st.button("Ver →", key=f"pl_ver_{nome}", use_container_width=True):
                st.session_state["pro_selected_patient"] = nome
                st.session_state.page = "pro_patient_detail"
                st.rerun()


def render(services: dict[str, Any], professional: Any) -> None:
    PatientsListRenderer(services, professional).render()
