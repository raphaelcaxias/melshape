"""
Melshape — Orchestrator Cascade.

Cascata de consequências que o Orchestrator executa após cada evento.

Uma ação do paciente pode gerar:
  - Metas impactadas (progresso atualizado)
  - Jornada avançada (se etapa concluída)
  - Badges desbloqueados
  - Alertas clínicos
  - Próximo passo recomendado
  - Notificações in-app

Arquitetura:
    CascadeMixin (herdado por Orchestrator)
    ├── Helpers (DRY)
    │   ├── _get_id(obj) -> str
    │   ├── _get_attr(obj, key, default) -> Any
    │   └── _get_health_mode(user) -> str
    ├── Core Cascade
    │   ├── _impact_goals(goal_type, result)
    │   ├── _update_journey(user, result)
    │   └── _check_badges(user, result)
    ├── Alert Strategy
    │   ├── _ALERT_STRATEGIES: dict[str, Callable]
    │   └── _check_alerts(user, result) -> dispatch
    ├── Next Step Chain
    │   ├── _NEXT_STEP_CHECKS: list[Callable]
    │   └── _generate_next_step(user, result) -> chain
    └── Notification
        └── _schedule_notification(user, result)

Princípios:
- DRY: helpers reutilizáveis eliminam ~40% do código duplicado
- Strategy Pattern: alertas por health_mode são registráveis
- Chain of Responsibility: próximo passo é uma cadeia de verificadores
- Decorator @safe_cascade: try/except unificado
- Tipagem forte: Protocol para Database e UserLike
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Protocol, TypeVar, cast, runtime_checkable

if TYPE_CHECKING:
    from services.orchestrator import OrchestratorResult

logger = logging.getLogger("Melshape.Cascade")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

_GOAL_TYPES: tuple[str, ...] = ("peso", "habito", "consistencia", "agua", "proteina")
_XP_GOAL_COMPLETED: int = 200
_RISK_ALERT_DAYS: int = 7
_HYDRATION_GOAL_ML: int = 2000
_DEFAULT_NEXT_STEP: str = "Continue consistente. Cada dia conta!"

# Tipo genérico para métodos do mixin
M = TypeVar("M", bound=Callable[..., None])


# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────────────────────

@runtime_checkable
class Database(Protocol):
    """Protocol para interface do banco de dados usada pelo Cascade."""
    is_real: bool
    client: Any
    
    def uid(self) -> str: ...
    def get_journey_ativa(self) -> Any: ...
    def get_goals(self, journey_id: str) -> list[Any]: ...
    def complete_stage(self, stage_id: str) -> None: ...
    def register_journey_achievement(self, journey_id: str, title: str, desc: str) -> None: ...
    def get_checkin_today(self) -> Any: ...
    def get_habits(self) -> list[Any]: ...
    def get_today_records(self) -> list[Any]: ...
    def get_hydration_today(self) -> float: ...
    def get_checkin_streak(self) -> int: ...
    def create_notification(self, message: str, tipo: str) -> None: ...


# Tipo flexível para usuário (dict ou objeto)
UserLike = dict[str, Any] | Any


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS (DRY)
# ─────────────────────────────────────────────────────────────────────────────

def _get_id(obj: Any) -> str:
    """Obtém ID de objeto ou dict de forma segura."""
    if obj is None:
        return ""
    if hasattr(obj, "id"):
        return str(obj.id)
    if isinstance(obj, dict):
        return str(obj.get("id", ""))
    return ""


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Obtém atributo de objeto ou dict de forma segura."""
    if obj is None:
        return default
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _get_health_mode(user: UserLike) -> str:
    """Obtém health_mode do usuário (dict ou objeto)."""
    return _get_attr(user, "health_mode", "general")


def _ensure_dict(obj: Any) -> dict[str, Any]:
    """Converte objeto para dicionário de forma segura."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return {"id": str(obj)}


def safe_cascade(fn: M) -> M:
    """
    Decorator que encapsula try/except + logging para métodos do Cascade.
    
    Reduz ~80% do boilerplate de tratamento de erros.
    """
    @wraps(fn)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return fn(self, *args, **kwargs)
        except Exception as e:
            logger.warning(f"{fn.__name__}: {e}")
            return None
    return cast(M, wrapper)


# ─────────────────────────────────────────────────────────────────────────────
# CASCADE MIXIN
# ─────────────────────────────────────────────────────────────────────────────

class CascadeMixin:
    """
    Mixin com a cascata de consequências compartilhadas.
    
    Requer self.db (Database) do Orchestrator.
    """
    db: Database
    
    # ─────────────────────────────────────────────────────────────────────────
    # METAS
    # ─────────────────────────────────────────────────────────────────────────
    
    @safe_cascade
    def _impact_goals(self, goal_type: str, result: "OrchestratorResult") -> None:
        """Impacta metas do tipo especificado."""
        if goal_type not in _GOAL_TYPES:
            logger.warning(f"_impact_goals: tipo inválido: {goal_type}")
            return
        
        journey = self.db.get_journey_ativa()
        journey_id = _get_id(journey)
        if not journey_id:
            return
        
        from services.goals_service import GoalsService
        goals_service = GoalsService(self.db)
        
        for goal in self.db.get_goals(journey_id):
            goal_data = _ensure_dict(goal)
            
            if goal_data.get("tipo") != goal_type or goal_data.get("concluida"):
                continue
            
            progress = goals_service.calculate_progress(goal_data)
            
            if progress.percentage >= 100:
                goal_id = goal_data.get("id", "")
                if goal_id:
                    goals_service.complete_goal(goal_id)
                    titulo = goal_data.get("titulo", "Meta")
                    result.new_badges.append(f"🎯 {titulo} concluída!")
                    result.xp_earned += _XP_GOAL_COMPLETED
    
    # ─────────────────────────────────────────────────────────────────────────
    # JORNADA
    # ─────────────────────────────────────────────────────────────────────────
    
    @safe_cascade
    def _update_journey(self, user: UserLike, result: "OrchestratorResult") -> None:
        """Atualiza a jornada do paciente — avança etapa se 100%."""
        journey = self.db.get_journey_ativa()
        journey_id = _get_id(journey)
        if not journey_id:
            return
        
        from services.journey_service import JourneyService
        progress = JourneyService(self.db).journey_progress(
            journey_id, _get_health_mode(user)
        )
        
        if progress.stage_progress_pct < 100 or not progress.pending_stages:
            return
        
        stage_id = _get_id(progress.current_stage)
        if not stage_id:
            return
        
        # Avança etapa
        self.db.complete_stage(stage_id)
        result.journey_advanced = True
        
        # Registra conquista
        stage_name = _get_attr(progress.current_stage, "nome", "")
        next_stage = progress.next_stage
        next_name = _get_attr(next_stage, "nome", "") if next_stage else ""
        
        self.db.register_journey_achievement(
            journey_id,
            f"Etapa concluída: {stage_name}",
            f"Avançou para {next_name}" if next_name else "Etapa concluída!",
        )
        
        if next_name:
            result.new_badges.append(f"🗺️ Nova etapa: {next_name}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # BADGES
    # ─────────────────────────────────────────────────────────────────────────
    
    @safe_cascade
    def _check_badges(self, user: UserLike, result: "OrchestratorResult") -> None:
        """Verifica e desbloqueia novas conquistas."""
        from services.gamification_service import GamificationService
        new_badges = GamificationService(self.db).check_achievements(user)
        result.new_badges.extend(new_badges)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ALERTAS (Strategy Pattern)
    # ─────────────────────────────────────────────────────────────────────────
    
    @safe_cascade
    def _check_alerts(self, user: UserLike, result: "OrchestratorResult") -> None:
        """
        Gera alertas clínicos usando Strategy Pattern.
        
        Novos modos de saúde podem ser adicionados apenas registrando
        uma função em _ALERT_STRATEGIES.
        """
        # Alerta de risco via RPC (sempre executado)
        self._check_risk_rpc()
        
        # Dispatch por health_mode
        health_mode = _get_health_mode(user)
        strategy = _ALERT_STRATEGIES.get(health_mode)
        if strategy:
            strategy(self, user, result)
    
    def _check_risk_rpc(self) -> None:
        """Chama RPC de alerta de risco no Supabase."""
        if not (self.db.is_real and self.db.client):
            return
        try:
            self.db.client.rpc("fn_alerta_risco", {"p_perfil_id": self.db.uid()}).execute()
        except Exception as e:
            logger.warning(f"_check_risk_rpc: {e}")
    
    # --- Alert Strategies ---
    
    def _alert_strategy_glp1(self, user: UserLike, result: "OrchestratorResult") -> None:
        """Strategy: alertas para modo GLP-1."""
        from services.glp1_service import GLP1Service
        from services.nutrition_service import NutritionService
        from services.nutrition_alerts import glp1_low_calorie_alert
        
        for alert_text in GLP1Service(self.db).symptom_alerts():
            result.alerts.append(("warning", alert_text))
        
        cal_alert = glp1_low_calorie_alert(NutritionService(self.db).daily_summary)
        if cal_alert:
            result.alerts.append(("warning", cal_alert))
    
    def _alert_strategy_bariatric(self, user: UserLike, result: "OrchestratorResult") -> None:
        """Strategy: alertas para modo bariátrico."""
        from services.bariatric_service import BariatricService
        
        phase_key = _get_attr(user, "bariatric_phase", "liquid")
        alerts = BariatricService(self.db).alerts(phase_key, user)
        
        for alert in alerts:
            result.alerts.append((alert.severity, alert.message))
    
    # ─────────────────────────────────────────────────────────────────────────
    # PRÓXIMO PASSO (Chain of Responsibility)
    # ─────────────────────────────────────────────────────────────────────────
    
    @safe_cascade
    def _generate_next_step(self, user: UserLike, result: "OrchestratorResult") -> None:
        """
        Gera o próximo passo recomendado usando Chain of Responsibility.
        
        Cada verificador da cadeia pode:
        - Retornar None → passa para o próximo
        - Retornar dict → define next_step e interrompe a cadeia
        """
        for check in _NEXT_STEP_CHECKS:
            step = check(self, user, result)
            if step:
                result.next_step = step["message"]
                result.next_step_page = step.get("page")
                result.next_step_type = step.get("type")
                return
        
        # Fallback: streak atual
        streak = result.streak or self.db.get_checkin_streak()
        if streak < 7:
            result.next_step = f"Continue! Faltam {7 - streak} dia(s) para 7 dias seguidos"
        else:
            result.next_step = f"🔥 {streak} dias seguidos! Continue assim."
        result.next_step_page = None
        result.next_step_type = None
    
    # --- Next Step Checks ---
    
    def _step_check_journey(self, user: UserLike, result: "OrchestratorResult") -> dict | None:
        """Verifica se não há jornada ativa."""
        journey = self.db.get_journey_ativa()
        if not journey or not _get_id(journey):
            return {"message": _DEFAULT_NEXT_STEP, "page": None, "type": None}
        return None
    
    def _step_check_checkin(self, user: UserLike, result: "OrchestratorResult") -> dict | None:
        """Verifica check-in pendente."""
        if not self.db.get_checkin_today():
            return {
                "message": "Faça seu check-in de hoje (30 segundos)",
                "page": "checkin",
                "type": None,
            }
        return None
    
    def _step_check_habits(self, user: UserLike, result: "OrchestratorResult") -> dict | None:
        """Verifica hábitos pendentes."""
        habits = self.db.get_habits()
        done_ids = {_get_id(r) for r in self.db.get_today_records()}
        pending = [h for h in habits if _get_id(h) not in done_ids]
        
        if pending:
            habit_name = _get_attr(pending[0], "nome", "Hábito")
            return {
                "message": f"Complete seu hábito: {habit_name}",
                "page": "habits",
                "type": None,
            }
        return None
    
    def _step_check_hydration(self, user: UserLike, result: "OrchestratorResult") -> dict | None:
        """Verifica meta de água."""
        water = self.db.get_hydration_today()
        if water < _HYDRATION_GOAL_ML:
            faltam = _HYDRATION_GOAL_ML - water
            return {
                "message": f"Registrar mais {faltam:.0f}ml de água",
                "page": "meals",
                "type": "hydration",
            }
        return None
    
    def _step_check_streak(self, user: UserLike, result: "OrchestratorResult") -> dict | None:
        """Verifica streak < 7 dias."""
        streak = result.streak or self.db.get_checkin_streak()
        if streak < 7:
            return {
                "message": f"Continue! Faltam {7 - streak} dia(s) para 7 dias seguidos",
                "page": None,
                "type": None,
            }
        return None
    
    # ─────────────────────────────────────────────────────────────────────────
    # NOTIFICAÇÃO
    # ─────────────────────────────────────────────────────────────────────────
    
    @safe_cascade
    def _schedule_notification(self, user: UserLike, result: "OrchestratorResult") -> None:
        """Cria notificação in-app."""
        if not result.notification_message:
            return
        self.db.create_notification(result.notification_message, tipo="engajamento")
        logger.debug(f"✅ Notificação criada: {result.notification_message[:50]}...")


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRIES (Strategy + Chain)
# ─────────────────────────────────────────────────────────────────────────────

# Strategy registry: health_mode -> método da CascadeMixin
_ALERT_STRATEGIES: dict[str, Callable[[CascadeMixin, UserLike, "OrchestratorResult"], None]] = {
    "glp1": CascadeMixin._alert_strategy_glp1,
    "bariatric": CascadeMixin._alert_strategy_bariatric,
}

# Chain of Responsibility: lista ordenada de verificadores
_NEXT_STEP_CHECKS: list[Callable[[CascadeMixin, UserLike, "OrchestratorResult"], dict | None]] = [
    CascadeMixin._step_check_journey,
    CascadeMixin._step_check_checkin,
    CascadeMixin._step_check_habits,
    CascadeMixin._step_check_hydration,
    CascadeMixin._step_check_streak,
]


__all__ = ["CascadeMixin"]
