"""
Melshape — Journey Service.

Serviço que gerencia a jornada do paciente: progresso, próximos passos,
marcos automáticos e inicialização da jornada.

Princípios:
- Jornada: sequência de etapas que o paciente percorre
- Progresso: cálculo automático baseado em dados reais
- Próximo passo: ação concreta e acionável para o paciente
- Marcos: conquistas automáticas ao atingir critérios
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    JourneyService
    ├── Inicialização
    │   ├── ensure_journey(user) -> Journey
    │   └── _create_initial_stages(journey_id, health_mode) -> None
    ├── Progresso
    │   ├── journey_progress(journey_id, health_mode) -> JourneyProgress
    │   ├── _calculate_stage_progress(stage, journey_id) -> int
    │   └── _empty_progress() -> JourneyProgress
    ├── Próximo Passo
    │   ├── next_step(stage, user) -> NextStep
    │   ├── _step_checkin() -> NextStep
    │   ├── _step_streak(streak) -> NextStep
    │   ├── _step_hydration(water_ml) -> NextStep
    │   ├── _step_meal() -> NextStep
    │   ├── _step_workout() -> NextStep
    │   ├── _step_glp1(user) -> NextStep | None
    │   ├── _step_bariatric(user) -> NextStep | None
    │   ├── _step_all_done(streak) -> NextStep
    │   └── _step_default() -> NextStep
    └── Marcos
        ├── check_automatic_milestones(journey_id, user) -> list[str]
        └── _build_milestone_candidates(streak, weights_df) -> list[MilestoneCandidate]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

import config
from core.database import Database
from core.models import Journey, Stage
from services.journey_data import _ETAPAS, _NOMES_JORNADA

logger = logging.getLogger("Melshape.Journey")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO DE JORNADA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class JourneyProgress:
    """
    Modelo de progresso da jornada.
    
    Attributes:
        current_stage: Etapa atual (ou última se todas concluídas)
        next_stage: Próxima etapa (ou None)
        completed_stages: Lista de etapas concluídas
        pending_stages: Lista de etapas pendentes
        total_stages: Total de etapas
        overall_progress_pct: Progresso geral (0-100)
        stage_progress_pct: Progresso da etapa atual (0-100)
    """
    current_stage: Stage | dict[str, Any]
    next_stage: Stage | dict[str, Any] | None
    completed_stages: list[Stage | dict[str, Any]]
    pending_stages: list[Stage | dict[str, Any]]
    total_stages: int
    overall_progress_pct: int
    stage_progress_pct: int
    
    @property
    def is_complete(self) -> bool:
        """Verifica se todas as etapas foram concluídas."""
        return len(self.pending_stages) == 0
    
    @property
    def remaining_stages(self) -> int:
        """Retorna número de etapas restantes."""
        return len(self.pending_stages)


@dataclass(frozen=True)
class NextStep:
    """
    Modelo de próximo passo acionável para o paciente.
    
    Attributes:
        action: Texto da ação a ser realizada
        icon: Emoji representativo
        page: Página para navegar (ou None)
        hub_type: Tipo de hub (meal/hydration/etc, ou None)
        urgency: Nível de urgência (alta/media/baixa/ok)
    """
    action: str
    icon: str
    page: str | None = None
    hub_type: str | None = None
    urgency: str = "ok"
    
    @property
    def is_urgent(self) -> bool:
        """Verifica se a ação é urgente."""
        return self.urgency == "alta"
    
    @property
    def has_navigation(self) -> bool:
        """Verifica se há navegação associada."""
        return self.page is not None
    
    @property
    def urgency_label(self) -> str:
        """Retorna rótulo da urgência."""
        labels = {
            "alta": "🔴 Alta",
            "media": "🟡 Média",
            "baixa": "🟢 Baixa",
            "ok": "✅ OK",
        }
        return labels.get(self.urgency, "✅ OK")


@dataclass(frozen=True)
class MilestoneCandidate:
    """
    Modelo de candidato a marco automático.
    
    Attributes:
        condition: Condição booleana para desbloqueio
        title: Título do marco
        description: Descrição do marco
    """
    condition: bool
    title: str
    description: str


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds de progresso
_STREAK_STAGE_1_DAYS: int = 1
_STREAK_STAGE_2_DAYS: int = 7
_STREAK_STAGE_3_DAYS: int = 30
_STREAK_STAGE_5_DAYS: int = 90

# Thresholds de hidratação
_HYDRATION_WARNING_ML: int = 1500
_HYDRATION_GOAL_ML: int = 2000

# Thresholds de refeições
_MIN_MEALS_PER_DAY: int = 3

# Marcos de streak
_MILESTONE_STREAK_7: int = 7
_MILESTONE_STREAK_30: int = 30
_MILESTONE_STREAK_90: int = 90

# Marcos de peso
_MILESTONE_WEIGHT_1: float = 1.0
_MILESTONE_WEIGHT_5: float = 5.0
_MILESTONE_WEIGHT_10: float = 10.0


# ─────────────────────────────────────────────────────────────────────────────
# JOURNEY SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class JourneyService:
    """
    Serviço de jornada do paciente.
    
    Gerencia progresso, próximos passos e marcos automáticos.
    
    Example:
        >>> db = Database()
        >>> journey_service = JourneyService(db)
        >>> journey = journey_service.ensure_journey(user)
        >>> progress = journey_service.journey_progress(journey.id, user.health_mode)
        >>> print(f"Etapa atual: {progress.current_stage.nome}")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de jornada.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ JourneyService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # INICIALIZAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def ensure_journey(self, user: dict[str, Any] | Any) -> Journey | dict[str, Any]:
        """
        Garante que o paciente tem uma jornada ativa.
        
        Se não tiver, cria automaticamente com as etapas do pilar.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto Journey ou dicionário com dados da jornada
            
        Example:
            >>> journey = journey_service.ensure_journey(user)
            >>> print(f"Jornada: {journey.nome} - {journey.tipo}")
        """
        if not user:
            logger.warning("ensure_journey: usuário não informado")
            return {}

        # Busca jornada ativa
        journey = self.db.get_journey_ativa()
        
        if journey:
            logger.debug(f"✅ Jornada ativa encontrada: {journey.id if hasattr(journey, 'id') else journey.get('id')}")
            return journey

        # Extrai dados do usuário
        health_mode = user.get("health_mode", "general") if isinstance(user, dict) else getattr(user, "health_mode", "general")
        journey_name = _NOMES_JORNADA.get(health_mode, "Minha Jornada")
        goal_weight = user.get("goal_weight", "") if isinstance(user, dict) else getattr(user, "goal_weight", "")
        objetivo = str(goal_weight) if goal_weight else ""

        logger.info(f"🔄 Criando nova jornada para {health_mode}: {journey_name}")
        
        # Cria nova jornada
        journey = self.db.create_journey(health_mode, journey_name, objetivo)

        if journey:
            journey_id = journey.id if hasattr(journey, "id") else journey.get("id", "")
            self._create_initial_stages(journey_id, health_mode)
            logger.info(f"✅ Jornada criada: {journey_id}")

        return journey or {}

    def _create_initial_stages(self, journey_id: str, health_mode: str) -> None:
        """
        Insere etapas padrão do pilar na tabela etapas_jornada.
        
        Args:
            journey_id: ID da jornada
            health_mode: Modo de saúde (general/fitness/bariatric/glp1)
        """
        if not journey_id:
            logger.warning("_create_initial_stages: journey_id não informado")
            return

        if not self.db.is_real or not self.db.client:
            logger.debug("_create_initial_stages: modo offline, pulando criação")
            return

        stages = _ETAPAS.get(health_mode, _ETAPAS["general"])

        try:
            for stage in stages:
                self.db.client.table("etapas_jornada").insert({
                    "jornada_id": journey_id,
                    "ordem": stage["ordem"],
                    "nome": stage["nome"],
                    "descricao": stage["descricao"],
                    "icone": stage["icone"],
                    "concluida": False,
                }).execute()

            logger.info(f"✅ {len(stages)} etapas criadas para jornada {journey_id}")

        except Exception as e:
            logger.error(f"_create_initial_stages falhou: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # PROGRESSO
    # ─────────────────────────────────────────────────────────────────────────

    def journey_progress(
        self,
        journey_id: str,
        health_mode: str,
    ) -> JourneyProgress:
        """
        Calcula progresso com base em dados reais do paciente.
        
        Args:
            journey_id: ID da jornada
            health_mode: Modo de saúde (general/fitness/bariatric/glp1)
            
        Returns:
            Objeto JourneyProgress com progresso completo
            
        Example:
            >>> progress = journey_service.journey_progress(journey_id, "general")
            >>> print(f"Etapa atual: {progress.current_stage.nome}")
            >>> print(f"Progresso geral: {progress.overall_progress_pct}%")
        """
        if not journey_id:
            logger.warning("journey_progress: journey_id não informado")
            return self._empty_progress()

        # Busca etapas do banco
        stages_db = self.db.get_stages(journey_id)
        stages_ref = _ETAPAS.get(health_mode, _ETAPAS["general"])

        # Se não há etapas no banco, usa referência in-memory
        if not stages_db:
            logger.debug(f"journey_progress: usando etapas de referência para {health_mode}")
            stages_db = [
                {**e, "concluida": False, "id": f"mock_{e['ordem']}"}
                for e in stages_ref
            ]

        # Separa concluídas e pendentes
        completed = [s for s in stages_db if self._is_stage_completed(s)]
        pending = [s for s in stages_db if not self._is_stage_completed(s)]

        # Determina etapa atual
        current_stage = pending[0] if pending else stages_db[-1]
        next_stage = pending[1] if len(pending) > 1 else None

        # Calcula progresso geral
        total = len(stages_db)
        overall_pct = int(len(completed) / total * 100) if total else 0

        # Calcula progresso da etapa atual
        stage_pct = self._calculate_stage_progress(current_stage, journey_id)

        progress = JourneyProgress(
            current_stage=current_stage,
            next_stage=next_stage,
            completed_stages=completed,
            pending_stages=pending,
            total_stages=total,
            overall_progress_pct=overall_pct,
            stage_progress_pct=stage_pct,
        )

        logger.debug(f"✅ Progresso calculado: {overall_pct}% geral, {stage_pct}% etapa atual")
        return progress

    def _is_stage_completed(self, stage: Stage | dict[str, Any]) -> bool:
        """
        Verifica se uma etapa está concluída.
        
        Args:
            stage: Objeto Stage ou dicionário
            
        Returns:
            True se concluída
        """
        if hasattr(stage, "concluida"):
            return stage.concluida
        return stage.get("concluida", False)

    def _empty_progress(self) -> JourneyProgress:
        """
        Retorna estrutura vazia de progresso.
        
        Returns:
            Objeto JourneyProgress vazio
        """
        return JourneyProgress(
            current_stage={},
            next_stage=None,
            completed_stages=[],
            pending_stages=[],
            total_stages=0,
            overall_progress_pct=0,
            stage_progress_pct=0,
        )

    def _calculate_stage_progress(
        self,
        stage: Stage | dict[str, Any],
        journey_id: str,
    ) -> int:
        """
        Estima % de conclusão da etapa atual com dados reais.
        
        Args:
            stage: Objeto Stage ou dicionário com dados da etapa
            journey_id: ID da jornada
            
        Returns:
            Percentual de progresso (0-100)
        """
        try:
            # Extrai ordem da etapa
            ordem = stage.get("ordem", 1) if isinstance(stage, dict) else getattr(stage, "ordem", 1)
            
            # Coleta dados do usuário
            streak = self.db.get_checkin_streak()
            meals = self.db.get_meals(30)
            weights = self.db.get_weights(30)
            xp = self.db.get_xp()

            # Etapa 1: Primeiros Passos
            if ordem == 1:
                return self._calculate_stage_1_progress(streak, weights, meals)

            # Etapa 2: Construindo o Hábito
            if ordem == 2:
                return self._calculate_stage_2_progress(streak)

            # Etapa 3: Consistência Real
            if ordem == 3:
                return self._calculate_stage_3_progress(streak)

            # Etapa 4: Transformação Visível
            if ordem == 4:
                return self._calculate_stage_4_progress(xp)

            # Etapa 5: Novo Padrão de Vida
            if ordem == 5:
                return self._calculate_stage_5_progress(streak)

        except Exception as e:
            logger.warning(f"_calculate_stage_progress falhou: {e}")

        return 0

    def _calculate_stage_1_progress(
        self,
        streak: int,
        weights: pd.DataFrame,
        meals: list,
    ) -> int:
        """Calcula progresso da Etapa 1: Primeiros Passos."""
        pontos = 0
        
        if streak >= _STREAK_STAGE_1_DAYS:
            pontos += 33
        
        if not weights.empty:
            pontos += 33
        
        if len(meals) >= 1:
            pontos += 34
        
        return min(100, pontos)

    def _calculate_stage_2_progress(self, streak: int) -> int:
        """Calcula progresso da Etapa 2: Construindo o Hábito."""
        return min(100, int(streak / _STREAK_STAGE_2_DAYS * 100))

    def _calculate_stage_3_progress(self, streak: int) -> int:
        """Calcula progresso da Etapa 3: Consistência Real."""
        return min(100, int(streak / _STREAK_STAGE_3_DAYS * 100))

    def _calculate_stage_4_progress(self, xp: int) -> int:
        """Calcula progresso da Etapa 4: Transformação Visível."""
        return min(100, int(xp / 1000 * 100))

    def _calculate_stage_5_progress(self, streak: int) -> int:
        """Calcula progresso da Etapa 5: Novo Padrão de Vida."""
        return min(100, int(streak / _STREAK_STAGE_5_DAYS * 100))

    # ─────────────────────────────────────────────────────────────────────────
    # PRÓXIMO PASSO
    # ─────────────────────────────────────────────────────────────────────────

    def next_step(
        self,
        stage: Stage | dict[str, Any],
        user: dict[str, Any] | Any,
    ) -> NextStep:
        """
        Retorna uma ação concreta e acionável para o paciente.
        
        Args:
            stage: Objeto Stage ou dicionário com dados da etapa atual
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto NextStep com ação recomendada
            
        Example:
            >>> step = journey_service.next_step(stage, user)
            >>> print(f"Próximo passo: {step.action}")
            >>> if step.has_navigation:
            ...     print(f"Ir para: {step.page}")
        """
        if not stage:
            return self._step_default()

        try:
            # Coleta dados
            checkin = self.db.get_checkin_today()
            streak = self.db.get_checkin_streak()
            meals = self.db.get_meals(7)
            water = self.db.get_hydration_today()
            health_mode = user.get("health_mode", "general") if isinstance(user, dict) else getattr(user, "health_mode", "general")
            ordem = stage.get("ordem", 1) if isinstance(stage, dict) else getattr(stage, "ordem", 1)

            # 1. Check-in pendente — prioridade máxima
            if not checkin:
                return self._step_checkin()

            # 2. Streak em risco (ordem <= 2 e streak < 7)
            if ordem <= 2 and streak < _STREAK_STAGE_2_DAYS:
                return self._step_streak(streak)

            # 3. Água abaixo de 1,5L
            if water < _HYDRATION_WARNING_ML:
                return self._step_hydration(water)

            # 4. Menos de 3 refeições hoje
            if len(meals) < _MIN_MEALS_PER_DAY:
                return self._step_meal()

            # 5. Contexto por pilar
            if health_mode == "glp1":
                step = self._step_glp1(user)
                if step:
                    return step

            if health_mode == "bariatric":
                step = self._step_bariatric(user)
                if step:
                    return step

            if health_mode == "fitness":
                treino = self.db.get_workout_today() if hasattr(self.db, 'get_workout_today') else None
                if not treino:
                    return self._step_workout()

            # 6. Tudo em dia
            return self._step_all_done(streak)

        except Exception as e:
            logger.error(f"next_step falhou: {e}")
            return self._step_default()

    def _step_checkin(self) -> NextStep:
        """Passo: fazer check-in."""
        return NextStep(
            action="Faça seu check-in de hoje (30 segundos)",
            icon="✅",
            page="checkin",
            hub_type=None,
            urgency="alta",
        )

    def _step_streak(self, streak: int) -> NextStep:
        """Passo: manter streak."""
        faltam = _STREAK_STAGE_2_DAYS - streak
        return NextStep(
            action=f"Manter sequência por mais {faltam} dia(s)",
            icon="🔥",
            page="checkin",
            hub_type=None,
            urgency="media",
        )

    def _step_hydration(self, water_ml: int) -> NextStep:
        """Passo: beber água."""
        faltam = _HYDRATION_GOAL_ML - water_ml
        return NextStep(
            action=f"Registrar mais {faltam}ml de água — meta: 2L",
            icon="💧",
            page="meals",
            hub_type="hydration",
            urgency="media",
        )

    def _step_meal(self) -> NextStep:
        """Passo: registrar refeição."""
        return NextStep(
            action="Registrar as refeições de hoje",
            icon="🍽️",
            page="meals",
            hub_type="meal",
            urgency="baixa",
        )

    def _step_workout(self) -> NextStep:
        """Passo: registrar treino."""
        return NextStep(
            action="Registre seu treino de hoje",
            icon="🏋️",
            page="habits",
            hub_type=None,
            urgency="media",
        )

    def _step_glp1(self, user: dict[str, Any] | Any) -> NextStep | None:
        """Passo: GLP-1 específico."""
        try:
            from services.glp1_service import GLP1Service
            
            medication = user.get("glp1_medication", "") if isinstance(user, dict) else getattr(user, "glp1_medication", "")
            glp1_service = GLP1Service(self.db)
            proxima = glp1_service.proxima_dose(medication)
            
            if proxima and proxima.lower() not in ("hoje", "amanhã"):
                return NextStep(
                    action=f"Próxima dose GLP-1: {proxima}",
                    icon="💉",
                    page="glp1",
                    hub_type=None,
                    urgency="media",
                )
        except Exception as e:
            logger.warning(f"_step_glp1 falhou: {e}")
        
        return None

    def _step_bariatric(self, user: dict[str, Any] | Any) -> NextStep | None:
        """Passo: Bariátrica específico."""
        try:
            phase_key = user.get("bariatric_phase", "liquid") if isinstance(user, dict) else getattr(user, "bariatric_phase", "liquid")
            phase_data = config.BARIATRIC_PHASES.get(phase_key, {})
            
            if phase_data:
                phase_name = phase_data.get("name", "")
                max_ml = phase_data.get("max_ml", "")
                
                return NextStep(
                    action=f"Fase {phase_name} — máx {max_ml}ml por refeição",
                    icon="🔪",
                    page="bariatric",
                    hub_type=None,
                    urgency="baixa",
                )
        except Exception as e:
            logger.warning(f"_step_bariatric falhou: {e}")
        
        return None

    def _step_all_done(self, streak: int) -> NextStep:
        """Passo: tudo em dia."""
        return NextStep(
            action=f"🔥 {streak} dias seguidos! Continue assim.",
            icon="⭐",
            page=None,
            hub_type=None,
            urgency="ok",
        )

    def _step_default(self) -> NextStep:
        """Passo padrão (fallback)."""
        return NextStep(
            action="Continue consistente. Cada dia conta!",
            icon="⭐",
            page=None,
            hub_type=None,
            urgency="ok",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # MARCOS AUTOMÁTICOS
    # ─────────────────────────────────────────────────────────────────────────

    def check_automatic_milestones(
        self,
        journey_id: str,
        user: dict[str, Any] | Any,
    ) -> list[str]:
        """
        Registra marcos automaticamente quando critérios são atingidos.
        
        Args:
            journey_id: ID da jornada
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Lista de títulos de marcos registrados
            
        Example:
            >>> new_milestones = journey_service.check_automatic_milestones(journey_id, user)
            >>> for milestone in new_milestones:
            ...     print(f"🏁 Novo marco: {milestone}")
        """
        if not journey_id:
            logger.warning("check_automatic_milestones: journey_id não informado")
            return []

        new_milestones = []

        try:
            # Coleta dados
            streak = self.db.get_checkin_streak()
            weights = self.db.get_weights(365)

            # Busca marcos existentes
            existing_milestones = self.db.get_milestones(journey_id)
            existing_titles = {
                m.titulo if hasattr(m, "titulo") else m.get("titulo", "")
                for m in existing_milestones
            }

            # Candidatos a marcos
            candidates = self._build_milestone_candidates(streak, weights)

            for candidate in candidates:
                if candidate.condition and candidate.title not in existing_titles:
                    self.db.register_milestone(journey_id, candidate.title, candidate.description)
                    new_milestones.append(candidate.title)
                    logger.info(f"🏁 Marco registrado: {candidate.title}")

        except Exception as e:
            logger.error(f"check_automatic_milestones falhou: {e}")

        if new_milestones:
            logger.info(f"✅ {len(new_milestones)} novo(s) marco(s) registrado(s)")

        return new_milestones

    def _build_milestone_candidates(
        self,
        streak: int,
        weights_df: pd.DataFrame,
    ) -> list[MilestoneCandidate]:
        """
        Monta lista de candidatos a marcos.
        
        Args:
            streak: Dias consecutivos
            weights_df: DataFrame com histórico de peso
            
        Returns:
            Lista de objetos MilestoneCandidate
        """
        candidates = [
            # Marcos de streak
            MilestoneCandidate(
                condition=streak >= _MILESTONE_STREAK_7,
                title="🔥 7 Dias Seguidos",
                description="Uma semana sem falhar!",
            ),
            MilestoneCandidate(
                condition=streak >= _MILESTONE_STREAK_30,
                title="🏆 30 Dias Seguidos",
                description="Um mês de consistência!",
            ),
            MilestoneCandidate(
                condition=streak >= _MILESTONE_STREAK_90,
                title="👑 90 Dias Seguidos",
                description="Três meses. Lendário.",
            ),
        ]

        # Adiciona marcos de peso
        if not weights_df.empty and len(weights_df) >= 2:
            try:
                first_weight = float(weights_df.iloc[0]["weight"])
                last_weight = float(weights_df.iloc[-1]["weight"])
                diff = first_weight - last_weight

                candidates.extend([
                    MilestoneCandidate(
                        condition=diff >= _MILESTONE_WEIGHT_1,
                        title="📉 1 kg eliminado",
                        description="O primeiro quilo foi o mais difícil.",
                    ),
                    MilestoneCandidate(
                        condition=diff >= _MILESTONE_WEIGHT_5,
                        title="💪 5 kg eliminados",
                        description="5 quilos a menos. Isso é real.",
                    ),
                    MilestoneCandidate(
                        condition=diff >= _MILESTONE_WEIGHT_10,
                        title="🔥 10 kg eliminados",
                        description="10 quilos. Transformação total.",
                    ),
                ])
            except Exception as e:
                logger.warning(f"Erro ao calcular marcos de peso: {e}")

        return candidates

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS AUXILIARES
    # ─────────────────────────────────────────────────────────────────────────

    def get_stages_by_pillar(self, health_mode: str) -> list[dict[str, Any]]:
        """
        Retorna etapas definidas para um pilar.
        
        Args:
            health_mode: Modo de saúde (general/fitness/bariatric/glp1)
            
        Returns:
            Lista de dicionários com etapas
            
        Example:
            >>> stages = journey_service.get_stages_by_pillar("general")
            >>> for s in stages:
            ...     print(f"{s['ordem']}: {s['nome']}")
        """
        if not health_mode:
            logger.warning("get_stages_by_pillar: health_mode não informado")
            return []
        
        stages = _ETAPAS.get(health_mode, _ETAPAS["general"])
        logger.debug(f"get_stages_by_pillar: {len(stages)} etapas para {health_mode}")
        return stages

    def get_journey_name_by_pillar(self, health_mode: str) -> str:
        """
        Retorna o nome da jornada para um pilar.
        
        Args:
            health_mode: Modo de saúde (general/fitness/bariatric/glp1)
            
        Returns:
            Nome da jornada
            
        Example:
            >>> name = journey_service.get_journey_name_by_pillar("general")
            >>> print(name)  # "Jornada de Emagrecimento"
        """
        if not health_mode:
            logger.warning("get_journey_name_by_pillar: health_mode não informado")
            return "Minha Jornada"
        
        name = _NOMES_JORNADA.get(health_mode, "Minha Jornada")
        logger.debug(f"get_journey_name_by_pillar: {name} para {health_mode}")
        return name


__all__ = [
    "JourneyService",
    "JourneyProgress",
    "NextStep",
    "MilestoneCandidate",
]
