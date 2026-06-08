"""Melshape — Gráficos Plotly reutilizáveis com tooltips clínicos."""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Optional

GOLD  = "#C9A84C"
STEEL = "#3D5A73"
GREEN = "#16a34a"
RED   = "#dc2626"
AMBER = "#f59e0b"


def calories_area_chart(df: pd.DataFrame, goal: int = 0) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["calories"],
        mode="lines+markers", name="Calorias",
        line=dict(color=GOLD, width=3),
        marker=dict(size=8, color=GOLD, line=dict(color="white", width=2)),
        fill="tozeroy", fillcolor="rgba(201,168,76,0.09)",
        hovertemplate="<b>%{x}</b><br>%{y} kcal<extra></extra>",
    ))
    if goal:
        fig.add_hline(
            y=goal, line_dash="dash", line_color=STEEL, line_width=1.5,
            annotation_text=f"Meta: {goal} kcal",
            annotation_position="bottom right",
            annotation_font_color=STEEL,
        )
    fig.update_layout(
        height=300, template="plotly_white", showlegend=False,
        xaxis_title="", yaxis_title="kcal",
        margin=dict(l=0, r=0, t=10, b=0),
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def protein_week_chart(df: pd.DataFrame, protein_goal: float = 0) -> None:
    fig = go.Figure()
    colors = [GREEN if v >= protein_goal else AMBER for v in df["protein"].tolist()]
    fig.add_trace(go.Bar(
        x=df["date"], y=df["protein"],
        marker_color=colors, name="Proteínas",
        hovertemplate="<b>%{x}</b><br>%{y:.1f}g proteína<extra></extra>",
    ))
    if protein_goal:
        fig.add_hline(
            y=protein_goal, line_dash="dash", line_color=GREEN, line_width=1.5,
            annotation_text=f"Meta: {protein_goal:.0f}g",
            annotation_position="bottom right",
        )
    fig.update_layout(
        height=260, template="plotly_white", showlegend=False,
        xaxis_title="", yaxis_title="g",
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def macros_pie_chart(protein: float, carbs: float, fat: float) -> None:
    fig = go.Figure(go.Pie(
        labels=["Proteínas", "Carboidratos", "Gorduras"],
        values=[protein * 4, carbs * 4, fat * 9],
        marker_colors=[GREEN, GOLD, STEEL],
        hole=0.46,
        textfont=dict(size=12),
        hovertemplate="<b>%{label}</b><br>%{value:.0f} kcal (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        height=270, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
        margin=dict(l=0, r=0, t=10, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def weight_line_chart(df: pd.DataFrame, goal_weight: Optional[float] = None) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["log_date"], y=df["weight"],
        mode="lines+markers", name="Peso",
        line=dict(color=GOLD, width=3),
        marker=dict(size=7, color=GOLD, line=dict(color="white", width=2)),
        fill="tozeroy", fillcolor="rgba(201,168,76,0.07)",
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>%{y:.1f} kg<extra></extra>",
    ))
    if len(df) >= 5:
        ma = df.sort_values("log_date")["weight"].rolling(5, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=df.sort_values("log_date")["log_date"], y=ma,
            mode="lines", name="Média móvel",
            line=dict(color=STEEL, width=2, dash="dot"),
            hovertemplate="Média: %{y:.1f} kg<extra></extra>",
        ))
    if goal_weight:
        fig.add_hline(
            y=goal_weight, line_dash="dash", line_color=GREEN, line_width=1.5,
            annotation_text=f"Meta: {goal_weight} kg",
            annotation_position="bottom right",
        )
    fig.update_layout(
        height=310, template="plotly_white",
        xaxis_title="", yaxis_title="kg",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=0, r=0, t=20, b=0),
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def period_bar_chart(periods: dict, title: str = "") -> None:
    fig = px.bar(
        x=list(periods.keys()),
        y=list(periods.values()),
        color=list(periods.keys()),
        color_discrete_sequence=[AMBER, GOLD, STEEL],
        template="plotly_white",
        text_auto=True,
        title=title,
    )
    fig.update_layout(
        height=250, showlegend=False,
        coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=40 if title else 10, b=0),
        yaxis_title="", xaxis_title="",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def hydration_area_chart(days_data: list) -> None:
    """Gráfico de hidratação dos últimos dias."""
    if not days_data:
        return
    df = pd.DataFrame(days_data)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["date"], y=df["ml"],
        marker_color=[GREEN if v >= 1500 else AMBER for v in df["ml"].tolist()],
        hovertemplate="<b>%{x}</b><br>%{y} ml<extra></extra>",
    ))
    fig.add_hline(y=2000, line_dash="dash", line_color=STEEL,
                  annotation_text="Meta: 2000 ml")
    fig.update_layout(
        height=220, template="plotly_white", showlegend=False,
        xaxis_title="", yaxis_title="ml",
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
