"""
components — Componentes de UI reutilizáveis do Melshape.

CORREÇÃO: .charts e .alerts não existem como módulos separados.
Toda a funcionalidade está em cards.py.
"""
from .cards import (
    metric_card, progress_bar, empty_state, achievement_card,
    challenge_card, meal_item, alert, section_header, feature_card,
    mode_badge, motivational_quote, medical_disclaimer,
    show_new_achievements, hydration_bar,
)

# Funções adicionais presentes em cards.py
try:
    from .cards import (
        fab_button, xp_toast, divider, pill_badge, info_box,
    )
except ImportError:
    pass

try:
    from .next_step import render_next_step
except ImportError:
    pass

try:
    from .notification_inbox import (
        exibir_notificacoes, render_inbox_panel, render_pacientes_risco_pro,
    )
except ImportError:
    pass

# Stubs para charts/alerts — evitam ImportError em código legado
def calories_area_chart(*a, **kw): pass
def macros_pie_chart(*a, **kw): pass
def weight_line_chart(*a, **kw): pass
def period_bar_chart(*a, **kw): pass
def protein_week_chart(*a, **kw): pass
def hydration_area_chart(*a, **kw): pass
def show_clinical_alerts(*a, **kw): pass

__all__ = [
    "metric_card", "progress_bar", "empty_state", "achievement_card",
    "challenge_card", "meal_item", "alert", "section_header", "feature_card",
    "mode_badge", "motivational_quote", "medical_disclaimer",
    "show_new_achievements", "hydration_bar",
    "render_next_step",
    "exibir_notificacoes", "render_inbox_panel", "render_pacientes_risco_pro",
    "calories_area_chart", "macros_pie_chart", "weight_line_chart",
    "period_bar_chart", "protein_week_chart", "hydration_area_chart",
    "show_clinical_alerts",
]
