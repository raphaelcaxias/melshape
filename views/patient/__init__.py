"""
views.patient — Alias para o pacote ``patient`` (telas do paciente).

Este módulo é um proxy: qualquer import de ``views.patient.X``
resolve para ``patient.X``.

Telas principais (todas expõem ``render(services, user)``)
----------------------------------------------------------
home              Dashboard / home do paciente
checkin           Fluxo de check-in diário
habits            Hábitos (alimentação, suplementos, treinos)
goals             Metas e progresso
bariatric         Módulo pós-bariátrica
glp1              Módulo GLP-1
onboarding        Onboarding inicial
profile           Perfil do paciente
achievements      Conquistas, desafios e ranking
journey           Jornada de saúde
journey_story     Histórias da jornada
complete_evolution Evolução completa
register_hub      Hub de registro rápido
share_card        Card de compartilhamento

Módulos auxiliares (sem render próprio — importados internamente)
-----------------------------------------------------------------
home_blocks, home_consistency, home_context, home_daily
habits_detail, habits_form, habits_suplementos, habits_today, habits_treinos
goals_form, bariatric_tabs, glp1_forms
checkin_done, checkin_result
evolution_clinico, evolution_gami, evolution_legal
achievements_challenges, achievements_ranking
journey_blocks, journey_timeline, journey_story_forms
onboarding_steps, register_hub_quick
"""

import sys
import importlib

_real = importlib.import_module("patient")
sys.modules.setdefault("views.patient", _real)

from patient import (  # noqa: E402
    achievements,
    bariatric,
    checkin,
    complete_evolution,
    glp1,
    goals,
    habits,
    home,
    journey,
    journey_story,
    onboarding,
    profile,
    register_hub,
    share_card,
)

__all__ = [
    "home",
    "checkin",
    "habits",
    "goals",
    "bariatric",
    "glp1",
    "onboarding",
    "profile",
    "achievements",
    "journey",
    "journey_story",
    "complete_evolution",
    "register_hub",
    "share_card",
]
