"""
patient — Telas do paciente no Melshape.

CORREÇÃO: removidos imports de módulos inexistentes (dashboard, meals,
weight, supplements, workout, analysis). Esses são nomes de ROTA no app.py,
não arquivos Python.
"""

from . import (
    achievements,
    achievements_challenges,
    achievements_ranking,
    bariatric,
    bariatric_tabs,
    bariatric_forms,
    checkin,
    checkin_done,
    checkin_result,
    complete_evolution,
    evolution_clinico,
    evolution_corpo,
    evolution_gami,
    evolution_legal,
    glp1,
    glp1_forms,
    goals,
    goals_form,
    habits,
    habits_detail,
    habits_form,
    habits_suplementos,
    habits_today,
    habits_treinos,
    home,
    home_blocks,
    home_consistency,
    home_context,
    home_daily,
    home_helpers,
    journey,
    journey_blocks,
    journey_story,
    journey_story_forms,
    journey_timeline,
    onboarding,
    onboarding_steps,
    profile,
    profile_tabs,
    register_hub,
    register_hub_quick,
    share_card,
)

__all__ = [
    "home", "checkin", "habits", "goals", "bariatric", "glp1",
    "onboarding", "profile", "achievements", "journey", "journey_story",
    "complete_evolution", "register_hub", "share_card",
]
