"""
views.components — Alias para o pacote ``components`` (componentes de UI).

Este módulo é um proxy: qualquer import de ``views.components.X``
resolve para ``components.X``.

Módulos disponíveis
-------------------
cards               Cards, métricas, badges, alertas, estado vazio
next_step           Widget de próxima ação recomendada
next_step_render    Lógica auxiliar do next_step
notification_inbox  Inbox de notificações (paciente e profissional)

ATENÇÃO: os módulos ``charts`` e ``alerts`` referenciados no __init__.py
original não existem como arquivos separados. Toda essa funcionalidade está
em ``cards.py``. Importe diretamente de ``views.components.cards``.
"""

import sys
import importlib

_real = importlib.import_module("components")
sys.modules.setdefault("views.components", _real)

from components.cards import (  # noqa: E402
    achievement_card,
    alert,
    challenge_card,
    divider,
    empty_state,
    fab_button,
    feature_card,
    hydration_bar,
    info_box,
    meal_item,
    medical_disclaimer,
    metric_card,
    mode_badge,
    motivational_quote,
    pill_badge,
    progress_bar,
    section_header,
    show_new_achievements,
    xp_toast,
)
from components.next_step import render_next_step  # noqa: E402
from components.notification_inbox import (  # noqa: E402
    exibir_notificacoes,
    render_inbox_panel,
    render_pacientes_risco_pro,
)

__all__ = [
    # cards
    "metric_card", "progress_bar", "empty_state", "achievement_card",
    "challenge_card", "meal_item", "alert", "section_header",
    "feature_card", "mode_badge", "motivational_quote", "medical_disclaimer",
    "show_new_achievements", "hydration_bar", "fab_button", "xp_toast",
    "divider", "pill_badge", "info_box",
    # next_step
    "render_next_step",
    # notification_inbox
    "exibir_notificacoes", "render_inbox_panel", "render_pacientes_risco_pro",
]
