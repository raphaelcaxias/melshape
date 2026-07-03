"""views.components.cards — alias para components.cards"""
from components.cards import *  # noqa: F401, F403
from components.cards import (
    metric_card, progress_bar, empty_state, achievement_card,
    challenge_card, meal_item, alert, section_header, feature_card,
    mode_badge, motivational_quote, medical_disclaimer,
    show_new_achievements, hydration_bar,
)
try:
    from components.cards import fab_button, xp_toast, divider, pill_badge, info_box
except ImportError:
    pass
