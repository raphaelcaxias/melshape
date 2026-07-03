"""
Melshape — Tela "O que meu profissional recomendou".

Fecha o loop clínico pelo lado do paciente:
profissional registra conduta → paciente vê → paciente age.

Constituição:
- Toda Ação Gera Consequência: a conduta do profissional não fica só no dashboard.
- O Profissional Toma Decisões: e o paciente recebe essas decisões de forma clara.
- Humanização: condutas técnicas viram orientações acolhedoras.
"""
from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from views.components.cards import alert, empty_state, section_header

logger = logging.getLogger("Melshape.PrescricoesView")

# ─────────────────────────────────────────────────────────────────────────────
# HUMANIZAÇÃO DOS TIPOS DE CONDUTA
# ─────────────────────────────────────────────────────────────────────────────
_TIPO_LABELS = {
    "orientacao":     ("💬", "Orientação",          "var(--info)"),
    "ajuste_dieta":   ("🥗", "Ajuste Alimentar",    "var(--success)"),
    "alerta":         ("⚠️", "Atenção Necessária",  "var(--warning)"),
    "encaminhamento": ("🏥", "Encaminhamento",       "var(--error)"),
    "elogio":         ("🌟", "Reconhecimento",       "var(--primary)"),
    "revisao":        ("🔄", "Revisão do Plano",     "var(--info)"),
    "prescricao":     ("📋", "Prescrição",           "var(--primary)"),
}

_MAX_CONDUTAS = 10
_MAX_PRESCRICOES = 3
_CACHE_TTL = 120


# ─────────────────────────────────────────────────────────────────────────────
# RENDERER
# ─────────────────────────────────────────────────────────────────────────────
class PrescricoesRenderer:
    """Exibe ao paciente o que o profissional recomendou."""

    def __init__(self, services: dict[str, Any], user: dict[str, Any]) -> None:
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.pro_nome = user.get("professional_name") or user.get("professional_email") or ""

    def render(self) -> None:
        header_sub = (
            f"Recomendações de {self.pro_nome}"
            if self.pro_nome
            else "O que seu profissional recomendou"
        )
        section_header("💬 Orientações do Profissional", header_sub)

        condutas = self._get_condutas()
        prescricao = self._get_prescricao()

        if not condutas and not prescricao:
            self._render_sem_dados()
            return

        # Prescrição ativa (destaque)
        if prescricao:
            self._render_prescricao_ativa(prescricao)
            st.divider()

        # Orientações recentes
        if condutas:
            self._render_condutas(condutas)

    # ── Helpers de dados ──────────────────────────────────────────────────────

    @st.cache_data(ttl=_CACHE_TTL)
    def _get_condutas(_self) -> list[dict]:
        try:
            if _self.db.is_real and _self.db.client:
                uid = _self.db.uid()
                r = (
                    _self.db.client.table("condutas_clinicas")
                    .select("titulo, descricao, tipo, data_conduta")
                    .eq("perfil_id", uid)
                    .order("data_conduta", desc=True)
                    .limit(_MAX_CONDUTAS)
                    .execute()
                )
                return r.data or []
            return _self.db._mock().get("condutas", [])
        except Exception as e:
            logger.error(f"_get_condutas: {e}")
            return []

    @st.cache_data(ttl=_CACHE_TTL)
    def _get_prescricao(_self) -> dict | None:
        try:
            if _self.db.is_real and _self.db.client:
                uid = _self.db.uid()
                r = (
                    _self.db.client.table("prescricoes")
                    .select("objetivo, data_inicio, observacoes")
                    .eq("perfil_id", uid)
                    .order("data_inicio", desc=True)
                    .limit(1)
                    .execute()
                )
                return r.data[0] if r.data else None
            # Fallback: tenta método direto se existir
            if hasattr(_self.db, "get_active_prescription"):
                p = _self.db.get_active_prescription(_self.db.uid())
                if p:
                    return p.to_dict() if hasattr(p, "to_dict") else p
            return None
        except Exception as e:
            logger.error(f"_get_prescricao: {e}")
            return None

    # ── Renderização ──────────────────────────────────────────────────────────

    def _render_sem_dados(self) -> None:
        empty_state(
            "💬",
            "Sem orientações ainda",
            "Quando seu profissional registrar uma orientação "
            "ou prescrição, ela aparecerá aqui.",
        )
        st.markdown(
            """
            <div style="font-size:0.82rem;color:var(--text-muted);
                text-align:center;margin-top:0.5rem;">
                💡 Compartilhe este app com seu profissional de saúde
                para receber acompanhamento personalizado.
            </div>
            """,
            unsafe_allow_html=True,
        )

    def _render_prescricao_ativa(self, presc: dict) -> None:
        objetivo = presc.get("objetivo", "")
        data = presc.get("data_inicio", "")[:10]
        obs = presc.get("observacoes", "")

        st.markdown(
            f"""
            <div class="metric-card fade-in"
                style="border-left:4px solid var(--primary);
                background:var(--primary-light);">
                <div style="font-size:0.74rem;font-weight:700;
                    text-transform:uppercase;letter-spacing:.06em;
                    color:var(--text-faint);margin-bottom:0.5rem;">
                    📋 Plano ativo desde {data}
                </div>
                <div style="font-size:1rem;font-weight:700;
                    color:var(--text);line-height:1.4;margin-bottom:0.4rem;">
                    {objetivo}
                </div>
                {f'<div style="font-size:0.84rem;color:var(--text-muted);margin-top:0.3rem;">{obs}</div>' if obs else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )

    def _render_condutas(self, condutas: list[dict]) -> None:
        st.markdown(
            f"""
            <div style="font-size:0.74rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.08em;color:var(--text-faint);margin-bottom:0.8rem;">
                Orientações recentes ({len(condutas)})
            </div>
            """,
            unsafe_allow_html=True,
        )

        for c in condutas:
            tipo = c.get("tipo", "orientacao")
            icon, label, cor = _TIPO_LABELS.get(tipo, ("💬", "Orientação", "var(--info)"))
            titulo = c.get("titulo", "")
            desc = c.get("descricao", "")
            data = c.get("data_conduta", "")[:10]

            desc_html = (
                f'<div style="font-size:0.84rem;color:var(--text-muted);'
                f'margin-top:0.3rem;line-height:1.5;">{desc}</div>'
                if desc else ""
            )

            st.markdown(
                f"""
                <div style="padding:0.85rem 1rem;border-left:3px solid {cor};
                    background:var(--surface);border-radius:0 var(--radius-md)
                    var(--radius-md) 0;margin-bottom:0.6rem;
                    box-shadow:var(--shadow-sm);">
                    <div style="display:flex;justify-content:space-between;
                        align-items:flex-start;">
                        <div style="flex:1;">
                            <div style="font-size:0.72rem;font-weight:700;
                                color:{cor};text-transform:uppercase;
                                letter-spacing:.04em;margin-bottom:0.25rem;">
                                {icon} {label}
                            </div>
                            <div style="font-size:0.92rem;font-weight:600;
                                color:var(--text);">{titulo}</div>
                            {desc_html}
                        </div>
                        <div style="font-size:0.74rem;color:var(--text-faint);
                            margin-left:1rem;white-space:nowrap;">{data}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render(services: dict[str, Any], user: dict[str, Any]) -> None:
    PrescricoesRenderer(services, user).render()
