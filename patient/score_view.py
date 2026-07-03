"""
Melshape — Tela de Score de Transformação (visão do paciente).

Exibe o score de forma visual, narrativa e acionável.
Evita tecnicidade: o paciente não vê "aderência 68%" — vê "Consistência: ótima".

Acessível via: página "score" (adicionada ao router e sidebar).

Constituição:
- Simplicidade na Superfície: backend sofisticado, UX simples
- Uma Única Ação Principal: a tela responde "o que posso melhorar agora?"
- Humanização: números viram linguagem motivadora
"""
from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from services.score_service import ScoreService, ScoreData, ScoreSummary
from views.components.cards import alert, empty_state, section_header

logger = logging.getLogger("Melshape.ScoreView")

# ─────────────────────────────────────────────────────────────────────────────
# LABELS HUMANIZADOS — números nunca chegam crus ao paciente
# ─────────────────────────────────────────────────────────────────────────────
_AREA_LABELS = {
    "adherence":  ("📅", "Consistência", "Quantos dias você manteve a rotina"),
    "engagement": ("⚡", "Engajamento",  "O quanto você participa ativamente"),
    "nutrition":  ("🍽️", "Alimentação",  "Qualidade dos registros nutricionais"),
    "behavior":   ("😊", "Bem-estar",    "Humor, energia e qualidade do sono"),
    "clinical":   ("📊", "Indicadores",  "Dados clínicos registrados"),
}

_FAIXAS = [
    (80, "var(--success)", "Excelente"),
    (60, "var(--primary)", "Bom"),
    (40, "var(--warning)", "Em progresso"),
    (0,  "var(--error)",   "Começando"),
]


def _cor_valor(val: float) -> str:
    for threshold, cor, _ in _FAIXAS:
        if val >= threshold:
            return cor
    return "var(--error)"


def _label_valor(val: float) -> str:
    for threshold, _, label in _FAIXAS:
        if val >= threshold:
            return label
    return "Começando"


# ─────────────────────────────────────────────────────────────────────────────
# RENDERER
# ─────────────────────────────────────────────────────────────────────────────
class ScoreRenderer:
    def __init__(self, services: dict[str, Any], user: dict[str, Any]) -> None:
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.svc = ScoreService(self.db)

    def render(self) -> None:
        section_header(
            "📊 Seu Score de Transformação",
            "Uma visão completa de como você está evoluindo",
        )

        summary = self._get_summary()
        score_data = self._get_score_data()

        if summary is None or (score_data and score_data.is_empty):
            self._render_sem_dados()
            return

        # ── Nível atual — destaque principal ─────────────────────────────────
        self._render_nivel(summary)

        st.divider()

        # ── Radar das 5 dimensões ─────────────────────────────────────────────
        if score_data and not score_data.is_empty:
            self._render_dimensoes(score_data)
        else:
            self._render_dimensoes_vazias()

        st.divider()

        # ── Narrativa: o que melhorar ─────────────────────────────────────────
        self._render_acao(summary, score_data)

    # ── Private ──────────────────────────────────────────────────────────────

    @st.cache_data(ttl=300)
    def _get_summary(_self) -> ScoreSummary | None:
        try:
            return _self.svc.get_score_summary()
        except Exception as e:
            logger.error(f"_get_summary: {e}")
            return None

    @st.cache_data(ttl=300)
    def _get_score_data(_self) -> ScoreData | None:
        try:
            return _self.svc.get_score()
        except Exception as e:
            logger.error(f"_get_score_data: {e}")
            return None

    def _render_sem_dados(self) -> None:
        empty_state(
            "📊",
            "Score em construção",
            "Continue fazendo check-ins e registrando hábitos. "
            "Seu score aparece após os primeiros dias de uso.",
        )
        if st.button("✅ Fazer check-in agora →", type="primary",
                     use_container_width=True, key="score_cta_checkin"):
            st.session_state.page = "checkin"
            st.rerun()

    def _render_nivel(self, summary: ScoreSummary) -> None:
        score_int = getattr(summary, "score_int", 0)
        level_icon = summary.level_icon
        level_label = summary.level_label
        level_color = summary.level_color
        pct = min(100, max(0, score_int))

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(
                f"""
                <div class="metric-card fade-in" style="text-align:center;
                    border-color:{level_color};padding:1.5rem 1rem;">
                    <div style="font-size:2.5rem;">{level_icon}</div>
                    <div style="font-family:var(--font-display);font-weight:800;
                        font-size:2.2rem;color:{level_color};line-height:1;">
                        {score_int}
                    </div>
                    <div style="font-size:0.76rem;color:var(--text-muted);
                        margin-top:0.2rem;">de 100 pontos</div>
                    <div style="font-size:0.88rem;color:{level_color};
                        font-weight:700;margin-top:0.4rem;">{level_label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                f"""
                <div class="metric-card fade-in" style="height:100%;">
                    <div style="font-size:0.78rem;font-weight:700;
                        text-transform:uppercase;letter-spacing:.06em;
                        color:var(--text-faint);margin-bottom:0.6rem;">
                        Progresso geral
                    </div>
                    <div class="progress-track" style="height:14px;margin-bottom:.5rem;">
                        <div class="progress-fill" style="width:{pct}%;
                            background:{level_color};height:100%;border-radius:9999px;">
                        </div>
                    </div>
                    <div style="display:flex;justify-content:space-between;
                        font-size:0.72rem;color:var(--text-faint);">
                        <span>0</span>
                        <span style="font-weight:700;color:{level_color};">
                            {pct}%
                        </span>
                        <span>100</span>
                    </div>
                    <div style="font-size:0.84rem;color:var(--text-muted);
                        margin-top:0.8rem;line-height:1.5;">
                        Área mais forte: <b style="color:var(--success);">
                        {summary.strongest_area}</b><br>
                        Maior oportunidade: <b style="color:var(--warning);">
                        {summary.weakest_area}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    def _render_dimensoes(self, data: ScoreData) -> None:
        st.markdown(
            """
            <div style="font-size:0.74rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.08em;color:var(--text-faint);margin-bottom:1rem;">
                As 5 dimensões da sua transformação
            </div>
            """,
            unsafe_allow_html=True,
        )

        dimensoes = [
            ("adherence",  data.adherence),
            ("engagement", data.engagement),
            ("nutrition",  data.nutrition),
            ("behavior",   data.behavior),
            ("clinical",   data.clinical),
        ]

        for area_key, valor in dimensoes:
            icon, label, desc = _AREA_LABELS.get(area_key, ("📊", area_key, ""))
            cor = _cor_valor(valor)
            status = _label_valor(valor)
            pct = min(100, max(0, int(valor)))

            st.markdown(
                f"""
                <div style="margin-bottom:0.9rem;">
                    <div style="display:flex;justify-content:space-between;
                        align-items:center;margin-bottom:0.3rem;">
                        <div>
                            <span style="font-size:1rem;">{icon}</span>
                            <span style="font-size:0.88rem;font-weight:600;
                                color:var(--text);margin-left:0.4rem;">{label}</span>
                            <span style="font-size:0.74rem;color:var(--text-faint);
                                margin-left:0.5rem;">{desc}</span>
                        </div>
                        <span style="font-size:0.82rem;font-weight:700;color:{cor};">
                            {status}
                        </span>
                    </div>
                    <div class="progress-track" style="height:8px;">
                        <div class="progress-fill" style="width:{pct}%;
                            background:{cor};height:100%;border-radius:9999px;
                            transition:width .6s ease;">
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Tenta plotly radar se disponível
        self._render_radar(dimensoes)

    def _render_radar(self, dimensoes: list) -> None:
        try:
            import plotly.graph_objects as go

            labels = [_AREA_LABELS[k][1] for k, _ in dimensoes]
            values = [min(100, max(0, v)) for _, v in dimensoes]
            values_closed = values + [values[0]]
            labels_closed = labels + [labels[0]]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=values_closed,
                theta=labels_closed,
                fill="toself",
                fillcolor="rgba(201,168,76,.15)",
                line=dict(color="#C9A84C", width=2),
                marker=dict(size=6, color="#C9A84C"),
                name="Seu score",
            ))
            fig.update_layout(
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(
                        visible=True, range=[0, 100],
                        tickfont=dict(size=9, color="#9CA3AF"),
                        gridcolor="rgba(156,163,175,.2)",
                    ),
                    angularaxis=dict(
                        tickfont=dict(size=11, color="#6B7280"),
                        gridcolor="rgba(156,163,175,.15)",
                    ),
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                height=320,
                margin=dict(t=20, b=20, l=40, r=40),
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass  # radar é melhoria — barras já são suficientes

    def _render_dimensoes_vazias(self) -> None:
        for area_key in ["adherence", "engagement", "nutrition", "behavior", "clinical"]:
            icon, label, desc = _AREA_LABELS[area_key]
            st.markdown(
                f"""
                <div style="margin-bottom:0.7rem;opacity:.5;">
                    <div style="font-size:0.88rem;color:var(--text-muted);">
                        {icon} {label}
                    </div>
                    <div class="progress-track" style="height:8px;">
                        <div class="progress-fill" style="width:0%;height:100%;
                            border-radius:9999px;"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    def _render_acao(self, summary: ScoreSummary, data: ScoreData | None) -> None:
        st.markdown(
            """
            <div style="font-size:0.74rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.08em;color:var(--text-faint);margin-bottom:0.8rem;">
                O que fazer agora
            </div>
            """,
            unsafe_allow_html=True,
        )

        weakest = summary.weakest_area if summary else "—"

        # Mapeia área fraca → ação e página
        _acoes = {
            "Consistência": ("✅", "Faça o check-in todos os dias. Cada dia conta para sua sequência.", "checkin"),
            "Engajamento":  ("📋", "Complete os hábitos do dia. Cada hábito concluído aumenta seu engajamento.", "habits"),
            "Alimentação":  ("🍽️", "Registre pelo menos 2 refeições por dia para melhorar esse indicador.", "meals"),
            "Bem-estar":    ("😊", "Registre como está se sentindo no check-in de amanhã — humor, energia e sono.", "checkin"),
            "Indicadores":  ("📊", "Registre seu peso e, se possível, adicione exames na tela de Evolução.", "evolution"),
        }

        icon, msg, page = _acoes.get(weakest, ("⭐", "Continue consistente — você está no caminho certo.", "home"))

        st.markdown(
            f"""
            <div class="metric-card fade-in" style="border-left:4px solid var(--primary);
                background:var(--primary-light);">
                <div style="display:flex;gap:0.8rem;align-items:flex-start;">
                    <span style="font-size:1.8rem;">{icon}</span>
                    <div>
                        <div style="font-size:0.78rem;color:var(--text-faint);
                            font-weight:700;text-transform:uppercase;letter-spacing:.04em;
                            margin-bottom:0.3rem;">
                            Foco em: {weakest}
                        </div>
                        <div style="font-size:0.92rem;color:var(--text);
                            font-weight:500;line-height:1.5;">
                            {msg}
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            f"{icon} Agir agora →",
            type="primary",
            use_container_width=True,
            key="score_acao_cta",
        ):
            st.session_state.page = page
            st.rerun()


def render(services: dict[str, Any], user: dict[str, Any]) -> None:
    ScoreRenderer(services, user).render()
