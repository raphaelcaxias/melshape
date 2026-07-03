"""
Melshape — Transformation Orchestrator.

O cérebro do MelShape. Uma ação do paciente dispara consequências em cascata
em todos os domínios: XP, badges, jornada, metas, notificações e alertas.

Princípios:
- Event-driven: cada ação do paciente é um evento
- Cascata: um evento gera múltiplas consequências
- Desacoplamento: cada domínio é independente
- Falha segura: se uma etapa falha, as outras continuam
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para resultados

Eventos suportados:
    - checkin: check-in diário
    - peso: registro de peso
    - habito: conclusão de hábito
    - refeicao: registro de refeição
    - agua: registro de hidratação
    - dose_glp1: registro de dose GLP-1
    - meta_concluida: conclusão de meta

Arquitetura:
    Orchestrator (ponto de entrada)
    ├── Event Processing
    │   ├── process(event, user, payload) -> OrchestratorResult
    │   └── _process_event(event, user, payload, result) -> None
    ├── Event Handlers
    │   ├── _handle_checkin(user, payload, result) -> None
    │   ├── _handle_weight(user, payload, result) -> None
    │   ├── _handle_habit(user, payload, result) -> None
    │   ├── _handle_meal(user, payload, result) -> None
    │   ├── _handle_water(user, payload, result) -> None
    │   ├── _handle_glp1_dose(user, payload, result) -> None
    │   └── _handle_goal_completed(user, payload, result) -> None
    ├── Cascade
    │   ├── _cascade(user, result) -> None
    │   ├── _update_journey(user) -> bool
    │   ├── _impact_goals(goal_type, result) -> None
    │   └── _get_alerts(user) -> list[AlertInfo]
    └── Helpers
        ├── _calculate_streak_bonus(streak) -> StreakBonus | None
        ├── _generate_checkin_message(streak) -> str
        └── _determine_next_step(user, result) -> NextStepInfo
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import config
from core.database import Database
from services.bariatric_service import BariatricService
from services.gamification_service import GamificationService
from services.glp1_service import GLP1Service
from services.goals_service import GoalsService
from services.habit_service import HabitService
from services.journey_service import JourneyService, NextStep
from services.nutrition_service import NutritionService
from services.score_service import ScoreService
from services.clinical_loop import ClinicalLoopService

logger = logging.getLogger("Melshape.Orchestrator")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# XP base por evento (usa config se disponível)
_XP_CHECKIN: int = getattr(config, "XP_CHECKIN", 20)
_XP_REFEICAO: int = getattr(config, "XP_REFEICAO", 5)
_XP_WEIGHT: int = getattr(config, "XP_WEIGHT", 30)
_XP_WATER: int = getattr(config, "XP_WATER", 10)
_XP_HABIT: int = getattr(config, "XP_HABIT", 15)
_XP_GLP1: int = getattr(config, "XP_GLP1", 25)
_XP_GOAL: int = getattr(config, "XP_GOAL", 200)
_XP_META_CONCLUIDA: int = getattr(config, "XP_META_CONCLUIDA", 200)

# Bônus de streak
_BONUS_STREAK_7: int = getattr(config, "XP_STREAK_7", 50)
_BONUS_STREAK_14: int = getattr(config, "XP_STREAK_14", 100)
_BONUS_STREAK_30: int = getattr(config, "XP_STREAK_30", 300)
_BONUS_STREAK_60: int = getattr(config, "XP_STREAK_60", 600)
_BONUS_STREAK_90: int = getattr(config, "XP_STREAK_90", 1000)

# Limite de água para meta diária
_WATER_GOAL_ML: int = getattr(config, "HYDRATION_GOAL_ML", 2000)

# Mensagens de check-in por streak
_CHECKIN_MESSAGES: dict[int, str] = {
    6: "🔥 Amanhã você completa 7 dias seguidos. Não quebre agora!",
    13: "⭐ Mais 1 dia para 14 dias consecutivos!",
    29: "🏆 Amanhã são 30 dias. Você está quase lá!",
}

# Mensagem padrão de check-in
_CHECKIN_DEFAULT_MESSAGE: str = "✅ {streak} dia(s) seguidos. Volte amanhã!"
_CHECKIN_FIRST_MESSAGE: str = "✅ Check-in feito! Comece sua sequência amanhã."


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class EventType(str, Enum):
    """Tipos de eventos suportados pelo orchestrator."""
    CHECKIN = "checkin"
    WEIGHT = "peso"
    HABIT = "habito"
    MEAL = "refeicao"
    WATER = "agua"
    GLP1_DOSE = "dose_glp1"
    GOAL_COMPLETED = "meta_concluida"
    
    @classmethod
    def from_string(cls, event: str) -> EventType | None:
        """Converte string para EventType."""
        try:
            return cls(event)
        except ValueError:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StreakBonus:
    """
    Modelo de bônus de streak.
    
    Attributes:
        streak_days: Dias de streak necessários
        xp: XP concedido
        reason: Motivo do bônus
        badge: Badge desbloqueado
    """
    streak_days: int
    xp: int
    reason: str
    badge: str
    
    @property
    def display_text(self) -> str:
        """Retorna texto formatado para exibição."""
        return f"🎁 Bônus de {self.streak_days} dias: +{self.xp} XP"


@dataclass(frozen=True)
class AlertInfo:
    """
    Modelo de informação de alerta.
    
    Attributes:
        severity: Severidade (info/warning/error)
        message: Mensagem do alerta
        source: Fonte do alerta (glp1/bariatric/system)
    """
    severity: str
    message: str
    source: str = "system"
    
    @property
    def is_critical(self) -> bool:
        """Verifica se é alerta crítico."""
        return self.severity == "error"
    
    @property
    def is_warning(self) -> bool:
        """Verifica se é alerta de atenção."""
        return self.severity == "warning"
    
    @property
    def severity_icon(self) -> str:
        """Retorna ícone da severidade."""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨",
        }
        return icons.get(self.severity, "ℹ️")


@dataclass(frozen=True)
class NextStepInfo:
    """
    Modelo de próximo passo recomendado.
    
    Attributes:
        action: Ação recomendada
        page: Página para navegar
        hub_type: Tipo do hub (meal/hydration/etc)
        priority: Prioridade (alta/media/baixa)
    """
    action: str
    page: str | None = None
    hub_type: str | None = None
    priority: str = "media"
    
    @property
    def has_navigation(self) -> bool:
        """Verifica se há navegação associada."""
        return self.page is not None
    
    @property
    def is_high_priority(self) -> bool:
        """Verifica se é alta prioridade."""
        return self.priority == "alta"


@dataclass(frozen=True)
class OrchestratorResult:
    """
    Resultado consolidado retornado para a view após um evento.
    
    Attributes:
        event_type: Tipo do evento processado
        xp_earned: XP ganho neste evento
        new_badges: Lista de badges desbloqueados
        new_milestones: Lista de marcos alcançados
        alerts: Lista de alertas gerados
        next_step: Próximo passo recomendado
        streak: Streak atual
        journey_advanced: Se a jornada avançou
        notification_message: Mensagem de notificação gerada
        success: Se o processamento foi bem-sucedido
        error_message: Mensagem de erro (se houver)
    """
    event_type: str = ""
    xp_earned: int = 0
    new_badges: list[str] = field(default_factory=list)
    new_milestones: list[str] = field(default_factory=list)
    alerts: list[AlertInfo] = field(default_factory=list)
    next_step: NextStepInfo | None = None
    streak: int = 0
    journey_advanced: bool = False
    notification_message: str = ""
    success: bool = True
    error_message: str = ""
    
    @property
    def has_xp(self) -> bool:
        """Verifica se ganhou XP."""
        return self.xp_earned > 0
    
    @property
    def has_badges(self) -> bool:
        """Verifica se ganhou badges."""
        return len(self.new_badges) > 0
    
    @property
    def has_milestones(self) -> bool:
        """Verifica se ganhou marcos."""
        return len(self.new_milestones) > 0
    
    @property
    def has_alerts(self) -> bool:
        """Verifica se há alertas."""
        return len(self.alerts) > 0
    
    @property
    def has_critical_alerts(self) -> bool:
        """Verifica se há alertas críticos."""
        return any(a.is_critical for a in self.alerts)
    
    @property
    def has_notification(self) -> bool:
        """Verifica se há mensagem de notificação."""
        return bool(self.notification_message)
    
    @property
    def has_next_step(self) -> bool:
        """Verifica se há próximo passo recomendado."""
        return self.next_step is not None
    
    @property
    def total_achievements(self) -> int:
        """Retorna total de conquistas (badges + marcos)."""
        return len(self.new_badges) + len(self.new_milestones)
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido do resultado."""
        parts = []
        if self.has_xp:
            parts.append(f"+{self.xp_earned} XP")
        if self.has_badges:
            parts.append(f"{len(self.new_badges)} badge(s)")
        if self.has_milestones:
            parts.append(f"{len(self.new_milestones)} marco(s)")
        if self.streak > 0:
            parts.append(f"🔥 {self.streak} dias")
        
        return " • ".join(parts) if parts else "Evento processado"


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

class Orchestrator:
    """
    Transformation Orchestrator — o cérebro do MelShape.
    
    Processa eventos do paciente e dispara consequências em cascata.
    
    Example:
        >>> db = Database()
        >>> orchestrator = Orchestrator(db)
        >>> user = st.session_state.user
        >>> result = orchestrator.process("checkin", user, {"humor": 4})
        >>> print(f"XP ganho: {result.xp_earned}")
        >>> if result.has_badges:
        ...     print(f"Badges: {result.new_badges}")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o orchestrator.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        self._gamification = GamificationService(db)
        self._journey = JourneyService(db)
        self._goals = GoalsService(db)
        self._nutrition = NutritionService(db)
        self._habit_service = HabitService(db)
        self._glp1_service = GLP1Service(db)
        self._bariatric_service = BariatricService(db)
        logger.debug("✅ Orchestrator inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # EVENT PROCESSING
    # ─────────────────────────────────────────────────────────────────────────

    def process(
        self,
        event: str,
        user: dict[str, Any] | Any,
        payload: dict[str, Any] | None = None,
    ) -> OrchestratorResult:
        """
        Processa um evento do paciente.
        
        Args:
            event: Tipo do evento (checkin/peso/habito/refeicao/agua/dose_glp1/meta_concluida)
            user: Objeto User ou dicionário com dados do usuário
            payload: Dados adicionais do evento
            
        Returns:
            OrchestratorResult com todas as consequências
            
        Example:
            >>> result = orchestrator.process("checkin", user, {"humor": 4})
            >>> print(result.summary_text)
        """
        if not event:
            logger.warning("process: event não informado")
            return OrchestratorResult(success=False, error_message="Event não informado")
        
        if not user:
            logger.warning("process: user não informado")
            return OrchestratorResult(success=False, error_message="User não informado")
        
        payload = payload or {}
        result = OrchestratorResult(event_type=event)
        
        try:
            # 1. Processa o evento específico
            self._process_event(event, user, payload, result)
            
            # 2. Cascata comum a todos os eventos
            self._cascade(user, result)
            
            logger.info(
                f"✅ Evento processado: {event} "
                f"(XP: {result.xp_earned}, Badges: {len(result.new_badges)}, "
                f"Alerts: {len(result.alerts)})"
            )
            
        except Exception as e:
            logger.error(f"Orchestrator ({event}): {e}", exc_info=True)
            result = OrchestratorResult(
                event_type=event,
                success=False,
                error_message=str(e),
            )
        
        return result

    def _process_event(
        self,
        event: str,
        user: dict[str, Any] | Any,
        payload: dict[str, Any],
        result: OrchestratorResult,
    ) -> None:
        """
        Processa o evento específico.
        
        Args:
            event: Tipo do evento
            user: Dados do usuário
            payload: Dados adicionais
            result: Resultado para preencher
        """
        handlers = {
            EventType.CHECKIN.value: self._handle_checkin,
            EventType.WEIGHT.value: self._handle_weight,
            EventType.HABIT.value: self._handle_habit,
            EventType.MEAL.value: self._handle_meal,
            EventType.WATER.value: self._handle_water,
            EventType.GLP1_DOSE.value: self._handle_glp1_dose,
            EventType.GOAL_COMPLETED.value: self._handle_goal_completed,
        }
        
        handler = handlers.get(event)
        if handler:
            handler(user, payload, result)
        else:
            logger.warning(f"_process_event: evento desconhecido: {event}")

    # ─────────────────────────────────────────────────────────────────────────
    # CASCADE (common to all events)
    # ─────────────────────────────────────────────────────────────────────────

    def _cascade(
        self,
        user: dict[str, Any] | Any,
        result: OrchestratorResult,
    ) -> None:
        """
        Executa cascata de consequências comum a todos os eventos.
        
        Args:
            user: Dados do usuário
            result: Resultado para preencher
        """
        try:
            # Atualiza jornada
            journey_advanced = self._update_journey(user)
            result.journey_advanced = journey_advanced
            
            # Verifica badges
            new_badges = self._gamification.check_achievements(user)
            result.new_badges.extend(new_badges)
            
            # Verifica alertas
            alerts = self._get_alerts(user)
            result.alerts.extend(alerts)
            
            # Gera próximo passo
            next_step = self._determine_next_step(user, result)
            result.next_step = next_step
            
            # Programa notificação
            if result.notification_message:
                self._create_notification(user, result.notification_message)

            # ELO 1: atualiza ScoreService para o profissional ver dado fresco
            try:
                score_svc = ScoreService(self.db)
                score_svc.invalidate_cache()
            except Exception as _se:
                logger.debug(f"ScoreService cache invalidation skipped: {_se}")

            # ELO 2: ClinicalLoop detecta alertas automáticos após cada evento
            try:
                uid = self.db.uid()
                if uid:
                    ClinicalLoopService(self.db).after_event(
                        event_type=result.event_type,
                        patient_id=uid,
                        user=user,
                        result=result,
                    )
            except Exception as _ce:
                logger.debug(f"ClinicalLoop after_event skipped: {_ce}")

            # ELO 3: email proativo se streak em risco (não checkin hoje + streak >= 3)
            try:
                if result.event_type != "checkin":
                    streak = getattr(result, "streak", 0) or 0
                    if streak >= 3:
                        email = self._get_user_email(user)
                        name  = self._get_user_name(user)
                        if email and name:
                            from services.email_service import send_streak_at_risk
                            send_streak_at_risk(email, name, streak)
            except Exception as _ee:
                logger.debug(f"Email proativo skipped: {_ee}")

            # Sprint 6: analytics — rastreia evento após cada ação do paciente
            try:
                from services.analytics_service import EventTracker
                uid = self._get_user_email(user) or ""
                pilar = user.get("health_mode", "general") if isinstance(user, dict) else getattr(user, "health_mode", "general")
                streak = getattr(result, "streak", 0) or 0
                tracker = EventTracker(self.db, uid)
                tracker.track(result.event_type, {"streak": streak, "pilar": pilar})
            except Exception as _ae:
                logger.debug(f"Analytics track skipped: {_ae}")

        except Exception as e:
            logger.error(f"_cascade falhou: {e}", exc_info=True)

    # ─────────────────────────────────────────────────────────────────────────
    # EVENT HANDLERS
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_checkin(
        self,
        user: dict[str, Any] | Any,
        payload: dict[str, Any],
        result: OrchestratorResult,
    ) -> None:
        """
        Processa evento de check-in.
        
        Args:
            user: Dados do usuário
            payload: Dados do check-in (humor, energia, sono, habito_id)
            result: Resultado para preencher
        """
        # XP do check-in
        self.db.add_xp(_XP_CHECKIN, motivo="checkin")
        result.xp_earned += _XP_CHECKIN
        
        # Streak
        result.streak = self.db.get_checkin_streak()
        
        # Bônus de streak
        bonus = self._calculate_streak_bonus(result.streak)
        if bonus:
            self.db.add_xp(bonus.xp, motivo=bonus.reason)
            result.xp_earned += bonus.xp
            result.new_badges.append(bonus.badge)
        
        # Se tiver hábito associado, processa
        habit_id = payload.get("habito_id")
        if habit_id:
            self._handle_habit(user, {"habito_id": habit_id}, result)
        
        # Impacta metas de consistência
        self._impact_goals("consistencia", result)
        
        # Gera mensagem de notificação
        result.notification_message = self._generate_checkin_message(result.streak)

    def _handle_weight(
        self,
        user: dict[str, Any] | Any,
        payload: dict[str, Any],
        result: OrchestratorResult,
    ) -> None:
        """
        Processa evento de registro de peso.
        
        Args:
            user: Dados do usuário
            payload: Dados do peso (peso)
            result: Resultado para preencher
        """
        self.db.add_xp(_XP_WEIGHT, motivo="pesagem")
        result.xp_earned += _XP_WEIGHT
        
        # Impacta metas de peso
        self._impact_goals("peso", result)

    def _handle_habit(
        self,
        user: dict[str, Any] | Any,
        payload: dict[str, Any],
        result: OrchestratorResult,
    ) -> None:
        """
        Processa evento de conclusão de hábito.
        
        Args:
            user: Dados do usuário
            payload: Dados do hábito (habito_id)
            result: Resultado para preencher
        """
        habit_id = payload.get("habito_id")
        if not habit_id:
            logger.warning("_handle_habit: habito_id não informado")
            return
        
        log_result = self._habit_service.log(habit_id)
        
        result.xp_earned += log_result.xp_earned
        
        if log_result.bonus_message:
            result.new_badges.append(log_result.bonus_message)
        
        # Impacta metas de hábito
        self._impact_goals("habito", result)

    def _handle_meal(
        self,
        user: dict[str, Any] | Any,
        payload: dict[str, Any],
        result: OrchestratorResult,
    ) -> None:
        """
        Processa evento de registro de refeição.
        
        Args:
            user: Dados do usuário
            payload: Dados da refeição
            result: Resultado para preencher
        """
        self.db.add_xp(_XP_REFEICAO, motivo="refeicao")
        result.xp_earned += _XP_REFEICAO
        
        # Impacta metas de proteína
        self._impact_goals("proteina", result)

    def _handle_water(
        self,
        user: dict[str, Any] | Any,
        payload: dict[str, Any],
        result: OrchestratorResult,
    ) -> None:
        """
        Processa evento de registro de água.
        
        Args:
            user: Dados do usuário
            payload: Dados da água (ml)
            result: Resultado para preencher
        """
        # Verifica se atingiu a meta diária
        current_total = self.db.get_hydration_today()
        
        if current_total >= _WATER_GOAL_ML:
            self.db.add_xp(_XP_WATER, motivo="meta_agua")
            result.xp_earned += _XP_WATER
        
        # Impacta metas de água
        self._impact_goals("agua", result)

    def _handle_glp1_dose(
        self,
        user: dict[str, Any] | Any,
        payload: dict[str, Any],
        result: OrchestratorResult,
    ) -> None:
        """
        Processa evento de registro de dose GLP-1.
        
        Args:
            user: Dados do usuário
            payload: Dados da dose
            result: Resultado para preencher
        """
        self.db.add_xp(_XP_GLP1, motivo="dose_glp1")
        result.xp_earned += _XP_GLP1
        
        result.notification_message = "💉 Dose registrada. Próxima em 7 dias."

    def _handle_goal_completed(
        self,
        user: dict[str, Any] | Any,
        payload: dict[str, Any],
        result: OrchestratorResult,
    ) -> None:
        """
        Processa evento de conclusão de meta.
        
        Args:
            user: Dados do usuário
            payload: Dados da meta (goal_id, titulo)
            result: Resultado para preencher
        """
        self.db.add_xp(_XP_META_CONCLUIDA, motivo="meta_concluida")
        result.xp_earned += _XP_META_CONCLUIDA
        
        titulo = payload.get("titulo", "")
        if titulo:
            result.new_badges.append(f"🎯 Meta concluída: {titulo}")

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _calculate_streak_bonus(self, streak: int) -> StreakBonus | None:
        """
        Calcula bônus de streak.
        
        Args:
            streak: Streak atual
            
        Returns:
            Objeto StreakBonus ou None
        """
        bonuses = {
            7: StreakBonus(
                streak_days=7,
                xp=_BONUS_STREAK_7,
                reason="streak_7",
                badge="📅 7 dias seguidos!"
            ),
            14: StreakBonus(
                streak_days=14,
                xp=_BONUS_STREAK_14,
                reason="streak_14",
                badge="🔥 14 dias!"
            ),
            30: StreakBonus(
                streak_days=30,
                xp=_BONUS_STREAK_30,
                reason="streak_30",
                badge="🏆 30 dias!"
            ),
            60: StreakBonus(
                streak_days=60,
                xp=_BONUS_STREAK_60,
                reason="streak_60",
                badge="💪 60 dias!"
            ),
            90: StreakBonus(
                streak_days=90,
                xp=_BONUS_STREAK_90,
                reason="streak_90",
                badge="👑 90 dias!"
            ),
        }
        return bonuses.get(streak)

    def _generate_checkin_message(self, streak: int) -> str:
        """
        Gera mensagem de notificação para check-in.
        
        Args:
            streak: Streak atual
            
        Returns:
            Mensagem de notificação
        """
        if streak in _CHECKIN_MESSAGES:
            return _CHECKIN_MESSAGES[streak]
        elif streak > 0:
            return _CHECKIN_DEFAULT_MESSAGE.format(streak=streak)
        return _CHECKIN_FIRST_MESSAGE

    def _impact_goals(self, goal_type: str, result: OrchestratorResult) -> None:
        """
        Impacta metas do tipo especificado.
        
        Args:
            goal_type: Tipo da meta (peso/habito/consistencia/agua/proteina)
            result: Resultado para preencher
        """
        try:
            journey = self.db.get_journey_ativa()
            if not journey:
                return
            
            journey_id = journey.id if hasattr(journey, "id") else journey.get("id", "")
            if not journey_id:
                return
            
            goals = self.db.get_goals(journey_id)
            
            for goal in goals:
                # Verifica se é objeto ou dict
                if hasattr(goal, "tipo"):
                    goal_type_attr = goal.tipo
                    is_completed = goal.concluida
                else:
                    goal_type_attr = goal.get("tipo", "")
                    is_completed = goal.get("concluida", False)
                
                if goal_type_attr != goal_type or is_completed:
                    continue
                
                progress = self._goals.calculate_progress(goal)
                
                if progress.percentage >= 100:
                    # Conclui meta
                    goal_id = goal.id if hasattr(goal, "id") else goal.get("id", "")
                    if goal_id:
                        self._goals.complete_goal(goal_id)
                        titulo = goal.titulo if hasattr(goal, "titulo") else goal.get("titulo", "Meta")
                        result.new_badges.append(f"🎯 {titulo} concluída!")
                        result.xp_earned += _XP_META_CONCLUIDA
                        
        except Exception as e:
            logger.warning(f"_impact_goals ({goal_type}): {e}")

    def _update_journey(self, user: dict[str, Any] | Any) -> bool:
        """
        Atualiza a jornada do paciente.
        
        Args:
            user: Dados do usuário
            
        Returns:
            True se avançou de etapa
        """
        try:
            journey = self.db.get_journey_ativa()
            if not journey:
                return False
            
            journey_id = journey.id if hasattr(journey, "id") else journey.get("id", "")
            if not journey_id:
                return False
            
            # Obtém health_mode
            if isinstance(user, dict):
                health_mode = user.get("health_mode", "general")
            else:
                health_mode = getattr(user, "health_mode", "general")
            
            progress = self._journey.journey_progress(journey_id, health_mode)
            
            if progress.stage_progress_pct >= 100 and progress.pending_stages:
                current_stage = progress.current_stage
                stage_id = current_stage.id if hasattr(current_stage, "id") else current_stage.get("id", "")
                
                if stage_id:
                    self.db.complete_stage(stage_id)
                    
                    # Registra conquista da jornada
                    stage_name = current_stage.nome if hasattr(current_stage, "nome") else current_stage.get("nome", "")
                    self.db.register_journey_achievement(
                        journey_id,
                        f'Etapa concluída: {stage_name}',
                        f'Avançou para próxima etapa',
                    )
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"_update_journey: {e}")
            return False

    def _get_alerts(self, user: dict[str, Any] | Any) -> list[AlertInfo]:
        """
        Obtém alertas para o usuário.
        
        Args:
            user: Dados do usuário
            
        Returns:
            Lista de objetos AlertInfo
        """
        alerts = []
        
        try:
            # Alerta de risco via RPC
            if self.db.is_real and self.db.client:
                try:
                    uid = self.db.uid()
                    self.db.client.rpc("fn_alerta_risco", {
                        "p_perfil_id": uid
                    }).execute()
                except Exception as e:
                    logger.warning(f"fn_alerta_risco: {e}")
            
            # Obtém health_mode
            if isinstance(user, dict):
                health_mode = user.get("health_mode", "general")
                is_glp1 = user.get("uses_glp1", False)
            else:
                health_mode = getattr(user, "health_mode", "general")
                is_glp1 = getattr(user, "uses_glp1", False)
            
            # Alerta GLP-1
            if health_mode == "glp1" or is_glp1:
                glp1_alerts = self._glp1_service.symptom_alerts()
                for alert in glp1_alerts:
                    alerts.append(AlertInfo(
                        severity="warning",
                        message=alert,
                        source="glp1",
                    ))
            
            # Alerta bariátrico
            if health_mode == "bariatric":
                if isinstance(user, dict):
                    phase_key = user.get("bariatric_phase", "liquid")
                else:
                    phase_key = getattr(user, "bariatric_phase", "liquid")
                
                bariatric_alerts = self._bariatric_service.alerts(phase_key, user)
                for alert in bariatric_alerts:
                    alerts.append(AlertInfo(
                        severity=alert.severity,
                        message=alert.message,
                        source="bariatric",
                    ))
                    
        except Exception as e:
            logger.warning(f"_get_alerts: {e}")
        
        return alerts

    def _determine_next_step(
        self,
        user: dict[str, Any] | Any,
        result: OrchestratorResult,
    ) -> NextStepInfo:
        """
        Gera próximo passo para o usuário.
        
        Args:
            user: Dados do usuário
            result: Resultado do evento
            
        Returns:
            Objeto NextStepInfo
        """
        try:
            # Verifica check-in pendente
            checkin_today = self.db.get_checkin_today()
            if not checkin_today:
                return NextStepInfo(
                    action="Faça seu check-in de hoje (30 segundos)",
                    page="checkin",
                    hub_type=None,
                    priority="alta",
                )
            
            # Verifica hábitos pendentes
            habits = self.db.get_habits()
            done_today = self.db.get_today_records()
            pending = [h for h in habits if h.id not in done_today]
            
            if pending:
                habit_name = pending[0].nome if hasattr(pending[0], "nome") else pending[0].get("nome", "Hábito")
                return NextStepInfo(
                    action=f"Complete seu hábito: {habit_name}",
                    page="habits",
                    hub_type=None,
                    priority="media",
                )
            
            # Verifica água
            water = self.db.get_hydration_today()
            if water < _WATER_GOAL_ML:
                faltam = _WATER_GOAL_ML - water
                return NextStepInfo(
                    action=f"Registrar mais {faltam}ml de água",
                    page="meals",
                    hub_type="hydration",
                    priority="media",
                )
            
            # Verifica streak
            streak = result.streak or self.db.get_checkin_streak()
            if streak < 7:
                faltam = 7 - streak
                return NextStepInfo(
                    action=f"Continue! Faltam {faltam} dia(s) para 7 dias seguidos",
                    page=None,
                    hub_type=None,
                    priority="baixa",
                )
            
            # Tudo em dia
            return NextStepInfo(
                action="Você está no caminho certo. Continue assim!",
                page=None,
                hub_type=None,
                priority="baixa",
            )
            
        except Exception as e:
            logger.warning(f"_determine_next_step: {e}")
            return NextStepInfo(
                action="Continue consistente. Cada dia conta!",
                page=None,
                hub_type=None,
                priority="baixa",
            )

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE USUÁRIO
    # ─────────────────────────────────────────────────────────────────────────

    def _get_user_email(self, user: dict | Any) -> str | None:
        """Extrai email do usuário de forma segura."""
        if hasattr(user, "email"):
            return user.email
        if isinstance(user, dict):
            return user.get("email")
        return None

    def _get_user_name(self, user: dict | Any) -> str | None:
        """Extrai nome do usuário de forma segura."""
        if hasattr(user, "name"):
            return user.name
        if isinstance(user, dict):
            return user.get("name")
        return None

    def _create_notification(
        self,
        user: dict[str, Any] | Any,
        message: str,
    ) -> None:
        """
        Cria notificação in-app.
        
        Args:
            user: Dados do usuário
            message: Mensagem da notificação
        """
        try:
            self.db.create_notification(message, tipo="engajamento")
            logger.debug(f"✅ Notificação criada: {message[:50]}...")
        except Exception as e:
            logger.warning(f"_create_notification: {e}")


__all__ = [
    "Orchestrator",
    "OrchestratorResult",
    "EventType",
    "StreakBonus",
    "AlertInfo",
    "NextStepInfo",
]
