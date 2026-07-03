"""
Melshape — Evolução Visual: gráficos de peso e humor ao longo do tempo.

Dados existem desde o início — nenhuma tabela nova necessária.
A tela transforma números em prova visual de progresso.

Constituição:
- Toda Ação Gera Consequência: o check-in de ontem aparece aqui hoje.
- Humanização: gráfico de humor não é "1-5" — é "como você foi evoluindo".
- Uma Única Ação Principal: cada tab tem um foco específico.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import streamlit as st

from views.components.cards import alert, empty_state, metric_card, section_header

logger = logging.getLogger("Melshape.EvolucaoVisual")

_CACHE_TTL = 120
_DIAS_PADRAO = 30
_MIN_PONTOS_GRAFICO = 3

_HUMOR_LABELS = {1: "😖 Péssimo", 2: "😕 Ruim", 3: "😐 Regular", 4: "🙂 Bom", 5: "😄 Ótimo"}
_ENERGIA_LABELS = {1: "😴", 2: "🥱", 3: "⚡", 4: "💪", 5: "🚀"}


class EvolucaoVisualRenderer:
    def __init__(self, services: dict[str, Any], user: dict[str, Any]) -> None:
        self.services = services
        self.user = user
        self.db = services.get("db")

    def render(self) -> None:
        section_header(
            "📈 Sua Evolução",
            "Cada ponto neste gráfico é um dia que você escolheu continuar",
        )

        dias = st.select_slider(
            "Período",
            options=[7, 14, 30, 60, 90],
            value=_DIAS_PADRAO,
            format_func=lambda x: f"Últimos {x} dias",
            key="ev_vis_dias",
            label_visibility="collapsed",
        )

        tab_peso, tab_humor, tab_habitos = st.tabs(
            ["⚖️ Peso", "😊 Bem-estar", "📋 Hábitos"]
        )

        with tab_peso:
            self._render_peso(dias)
        with tab_humor:
            self._render_humor(dias)
        with tab_habitos:
            self._render_habitos(dias)

    # ── PESO ────────────────────────────────────────────────────────────────

    def _render_peso(self, dias: int) -> None:
        pesos = self._get_pesos(dias)

        if not pesos or len(pesos) < _MIN_PONTOS_GRAFICO:
            empty_state(
                "⚖️",
                "Poucos registros de peso",
                f"Registre seu peso por pelo menos {_MIN_PONTOS_GRAFICO} dias "
                "para ver a evolução aqui.",
            )
            if st.button("⚖️ Registrar peso agora →", use_container_width=True,
                         key="ev_peso_cta"):
                st.session_state.page = "meals"
                st.session_state.hub_tipo = "weight"
                st.rerun()
            return

        # Métricas resumidas
        primeiro = pesos[0]["weight"]
        ultimo = pesos[-1]["weight"]
        variacao = ultimo - primeiro
        meta = float(self.user.get("goal_weight", ultimo))
        falta_meta = ultimo - meta

        col1, col2, col3 = st.columns(3)
        with col1:
            metric_card(f"{ultimo:.1f} kg", "Peso atual", "⚖️")
        with col2:
            cor = "success" if variacao <= 0 else "warning"
            sinal = "+" if variacao > 0 else ""
            metric_card(f"{sinal}{variacao:.1f} kg", f"Variação {dias}d", "📉", cor)
        with col3:
            if abs(falta_meta) < 0.5:
                metric_card("🎯 Meta!", "Peso objetivo", "🏆", "success")
            else:
                sinal = "-" if falta_meta > 0 else "+"
                metric_card(f"{sinal}{abs(falta_meta):.1f} kg", "Para a meta", "🎯")

        # Gráfico
        self._plotar_linha(
            x=[p["log_date"] for p in pesos],
            y=[p["weight"] for p in pesos],
            titulo="Evolução de Peso",
            y_label="Peso (kg)",
            cor="#C9A84C",
            meta_valor=meta if meta != ultimo else None,
            meta_label=f"Meta: {meta:.1f} kg",
        )

        # Mensagem motivacional contextual
        if variacao < -2:
            alert(f"🎉 Você eliminou {abs(variacao):.1f} kg neste período. Continue!", "success")
        elif variacao < 0:
            alert(f"📉 Queda de {abs(variacao):.1f} kg. O progresso está acontecendo.", "success")
        elif variacao > 2:
            alert("⚖️ Variação de peso detectada. Considere conversar com seu profissional.", "warning")

    # ── HUMOR / BEM-ESTAR ────────────────────────────────────────────────────

    def _render_humor(self, dias: int) -> None:
        checkins = self._get_checkins(dias)

        if not checkins or len(checkins) < _MIN_PONTOS_GRAFICO:
            empty_state(
                "😊",
                "Poucos check-ins registrados",
                "Faça check-ins diários para ver como seu bem-estar evolui.",
            )
            if st.button("✅ Fazer check-in agora →", type="primary",
                         use_container_width=True, key="ev_humor_cta"):
                st.session_state.page = "checkin"
                st.rerun()
            return

        # Métricas
        humores = [c["humor"] for c in checkins if c.get("humor")]
        energias = [c["energia"] for c in checkins if c.get("energia")]
        sonos = [c.get("qualidade_sono", 0) for c in checkins if c.get("qualidade_sono")]

        media_humor = sum(humores) / len(humores) if humores else 0
        media_energia = sum(energias) / len(energias) if energias else 0
        media_sono = sum(sonos) / len(sonos) if sonos else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            cor = "success" if media_humor >= 4 else "warning" if media_humor >= 3 else "error"
            metric_card(
                f"{_ENERGIA_LABELS.get(round(media_humor), '😐')} {media_humor:.1f}",
                "Humor médio", "😊", cor,
            )
        with col2:
            cor = "success" if media_energia >= 4 else "warning" if media_energia >= 3 else "error"
            metric_card(
                f"{_ENERGIA_LABELS.get(round(media_energia), '⚡')} {media_energia:.1f}",
                "Energia média", "⚡", cor,
            )
        with col3:
            cor = "success" if media_sono >= 4 else "warning" if media_sono >= 3 else "error"
            metric_card(f"{media_sono:.1f}/5", "Qualidade do sono", "😴", cor)

        # Gráfico multi-linha
        self._plotar_multilinhas(
            x=[c["data_checkin"] for c in checkins],
            series=[
                ([c.get("humor", 0) for c in checkins], "Humor", "#C9A84C"),
                ([c.get("energia", 0) for c in checkins], "Energia", "#22C55E"),
                ([c.get("qualidade_sono", 0) for c in checkins], "Sono", "#60A5FA"),
            ],
            titulo="Evolução do Bem-estar",
            y_label="Nível (1-5)",
            y_range=[0, 5.5],
        )

        # Tendência
        if len(humores) >= 7:
            recente = humores[-7:]
            anterior = humores[:7] if len(humores) >= 14 else humores[:len(humores)//2]
            if anterior:
                diff = sum(recente)/len(recente) - sum(anterior)/len(anterior)
                if diff >= 0.5:
                    alert("📈 Seu humor melhorou na última semana. Continue assim!", "success")
                elif diff <= -0.5:
                    alert("💙 Seu humor caiu um pouco. O que pode estar influenciando? Compartilhe no próximo check-in.", "info")

    # ── HÁBITOS ──────────────────────────────────────────────────────────────

    def _render_habitos(self, dias: int) -> None:
        habitos = self.db.get_habits() if self.db else []
        if not habitos:
            empty_state(
                "📋",
                "Nenhum hábito criado",
                "Crie hábitos para ver sua aderência ao longo do tempo.",
            )
            if st.button("📋 Criar hábitos →", use_container_width=True,
                         key="ev_hab_cta"):
                st.session_state.page = "habits"
                st.rerun()
            return

        # Aderência por hábito nos últimos N dias
        st.markdown(
            f"""
            <div style="font-size:0.74rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.08em;color:var(--text-faint);margin-bottom:0.9rem;">
                Aderência por hábito (últimos {dias} dias)
            </div>
            """,
            unsafe_allow_html=True,
        )

        from services.habit_service import HabitService
        svc = HabitService(self.db)

        dados_barras = []
        for h in habitos[:8]:
            aderencia = svc.adherence(h.id, days=dias)
            dados_barras.append((h.icone or "⭐", h.nome, aderencia))

        # Barras horizontais
        for icone, nome, pct in sorted(dados_barras, key=lambda x: x[2], reverse=True):
            cor = "var(--success)" if pct >= 80 else "var(--primary)" if pct >= 50 else "var(--warning)"
            pct_int = min(100, max(0, int(pct)))
            st.markdown(
                f"""
                <div style="margin-bottom:0.8rem;">
                    <div style="display:flex;justify-content:space-between;
                        align-items:center;margin-bottom:0.25rem;">
                        <span style="font-size:0.86rem;color:var(--text);">
                            {icone} {nome[:30]}
                        </span>
                        <span style="font-size:0.82rem;font-weight:700;color:{cor};">
                            {pct_int}%
                        </span>
                    </div>
                    <div class="progress-track" style="height:8px;">
                        <div class="progress-fill" style="width:{pct_int}%;
                            background:{cor};height:100%;border-radius:9999px;">
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Melhor e pior hábito
        if dados_barras:
            melhor = max(dados_barras, key=lambda x: x[2])
            pior = min(dados_barras, key=lambda x: x[2])
            if melhor[2] >= 70:
                alert(f"🏆 {melhor[0]} {melhor[1]}: sua maior consistência ({melhor[2]:.0f}%)", "success")
            if pior[2] < 40 and pior[0] != melhor[0]:
                alert(f"💡 {pior[0]} {pior[1]}: mais atenção aqui ({pior[2]:.0f}%)", "info")

    # ── Dados com cache ───────────────────────────────────────────────────────

    @st.cache_data(ttl=_CACHE_TTL)
    def _get_pesos(_self, dias: int) -> list[dict]:
        try:
            df = _self.db.get_weights(dias)
            if df is None or df.empty:
                return []
            return df[["log_date", "weight"]].to_dict("records")
        except Exception as e:
            logger.error(f"_get_pesos: {e}")
            return []

    @st.cache_data(ttl=_CACHE_TTL)
    def _get_checkins(_self, dias: int) -> list[dict]:
        try:
            if _self.db.is_real and _self.db.client:
                uid = _self.db.uid()
                inicio = (date.today() - timedelta(days=dias)).isoformat()
                r = (
                    _self.db.client.table("checkins")
                    .select("data_checkin, humor, energia, qualidade_sono")
                    .eq("perfil_id", uid)
                    .gte("data_checkin", inicio)
                    .order("data_checkin")
                    .limit(dias)
                    .execute()
                )
                return r.data or []
            return []
        except Exception as e:
            logger.error(f"_get_checkins: {e}")
            return []

    # ── Plotly helpers ────────────────────────────────────────────────────────

    def _plotar_linha(
        self,
        x: list,
        y: list,
        titulo: str,
        y_label: str,
        cor: str,
        meta_valor: float | None = None,
        meta_label: str = "",
    ) -> None:
        try:
            import plotly.graph_objects as go

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x, y=y,
                mode="lines+markers",
                line=dict(color=cor, width=2.5),
                marker=dict(size=6, color=cor),
                fill="tozeroy",
                fillcolor=f"rgba(201,168,76,.08)",
                name=y_label,
                hovertemplate="%{x}<br><b>%{y:.1f}</b><extra></extra>",
            ))
            if meta_valor is not None:
                fig.add_hline(
                    y=meta_valor,
                    line_dash="dash",
                    line_color="rgba(34,197,94,.6)",
                    annotation_text=meta_label,
                    annotation_font_color="rgba(34,197,94,.8)",
                    annotation_position="bottom right",
                )
            fig.update_layout(
                title=titulo,
                xaxis_title="Data",
                yaxis_title=y_label,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#9CA3AF",
                showlegend=False,
                height=320,
                margin=dict(t=40, b=30, l=30, r=10),
                hovermode="x unified",
            )
            fig.update_xaxes(gridcolor="rgba(0,0,0,0.05)", showgrid=True)
            fig.update_yaxes(gridcolor="rgba(0,0,0,0.05)", showgrid=True)
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            # Fallback sem Plotly — tabela simples
            st.markdown("**Registros:**")
            for xi, yi in zip(x[-10:], y[-10:]):
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:.3rem 0;border-bottom:1px solid var(--border-subtle);">'
                    f'<span>{xi}</span><b>{yi}</b></div>',
                    unsafe_allow_html=True,
                )
        except Exception as e:
            logger.error(f"_plotar_linha: {e}")

    def _plotar_multilinhas(
        self,
        x: list,
        series: list[tuple],
        titulo: str,
        y_label: str,
        y_range: list | None = None,
    ) -> None:
        try:
            import plotly.graph_objects as go

            fig = go.Figure()
            for y_vals, nome, cor in series:
                fig.add_trace(go.Scatter(
                    x=x, y=y_vals,
                    mode="lines+markers",
                    name=nome,
                    line=dict(color=cor, width=2),
                    marker=dict(size=5, color=cor),
                    hovertemplate=f"{nome}: %{{y:.1f}}<extra></extra>",
                ))
            layout = dict(
                title=titulo,
                yaxis_title=y_label,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#9CA3AF",
                height=320,
                margin=dict(t=40, b=30, l=30, r=10),
                hovermode="x unified",
                legend=dict(orientation="h", y=1.1),
            )
            if y_range:
                layout["yaxis"] = dict(range=y_range)
            fig.update_layout(**layout)
            fig.update_xaxes(gridcolor="rgba(0,0,0,0.05)")
            fig.update_yaxes(gridcolor="rgba(0,0,0,0.05)")
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"_plotar_multilinhas: {e}")


def render(services: dict[str, Any], user: dict[str, Any]) -> None:
    EvolucaoVisualRenderer(services, user).render()
