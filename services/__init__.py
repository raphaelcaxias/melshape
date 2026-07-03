"""
Services — Pacote de serviços de negócio.

Contém toda a lógica de negócio do Melshape:
- Orchestrator: processa eventos e dispara cascatas
- Nutrition, Gamification, Journey, Habit, GLP1, Bariatric, Score
- Professional, Plan, Payment, Notification, Relapse, Clinical Loop
- Evolution, Consultation Summary, Analytics, Food, Demo, Email
- Goals, Contextualizer, Streak Utils, etc.
"""

from .nutrition_service import NutritionService
from .gamification_service import GamificationService
from .food_service import FoodService
from .plan_service import PlanService
from .professional_service import ProfessionalService

__all__ = [
    "NutritionService",
    "GamificationService",
    "FoodService",
    "PlanService",
    "ProfessionalService",
]
