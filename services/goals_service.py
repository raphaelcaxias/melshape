"""
Melshape — Goals Service.

Serviço para gerenciamento de metas do paciente com progresso calculado
automaticamente a partir de dados reais do banco.

Princípios:
- Meta: objetivo concreto com progresso mensurável
- Progresso automático: calculado a partir de dados reais (peso, hábitos, etc.)
- Conclusão: meta concluída automaticamente quando atinge 100%
- Templates: sugestões de metas por tipo
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Tipos de meta suportados:
    - peso: progresso baseado em pesagens (redução ou ganho)
    - habito: progresso baseado em dias com hábitos registrados
    - consistencia: progresso baseado em streak de check-ins
    - agua: progresso baseado em dias com meta de água atingida
    - proteina: progresso baseado em média de proteína (7d)
    - livre: progresso manual (controlado pelo paciente)

Arquitetura:
    GoalsService
    ├── Templates
    │   ├── templates() -> dict[str, list[GoalTemplate]]
    │   ├── tipo_labels() -> dict[str, tuple[str, str]]
    │   └── get_templates_by_type(tipo) -> list[GoalTemplate]
    ├── Progresso
    │   ├── calculate_progress(goal) -> GoalProgress
    │   ├── _calculate_goal_status(progress, goal) -> str
    │   └── _calculate_*_progress() -> dict
    ├── Conclusão
    │   ├── complete_goal(goal_id) -> bool
    │   └── is_goal_achievable(goal) -> bool
    ├── Metas do Paciente
    │   ├── get_patient_goals(user) -> list[Goal]
    │   ├── get_active_goals(user) -> list[Goal]
    │   ├── get_completed_goals(user) -> list[Goal]
    │   └── get_goal_summary(user) -> GoalSummary
    └── Utilitários
        ├── get_goal_by_id(goal_id) -> Goal | None
        ├── days_remaining(prazo) -> int | None
        ├── goal_status(goal) -> str
        └── get_best_goal_type(user) -> str | None
"""
from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import config
import pandas as pd

from core.database import Database
from core.models import Goal

# Tenta importar calculators, se não existir usa fallbacks
try:
    from services.goals_calculators import (
        calc_agua,
        calc_consistencia,
        calc_habito,
        calc_peso,
        calc_proteina,
    )
    _HAS_CALCULATORS = True
except ImportError:
    _HAS_CALCULATORS = False

logger = logging.getLogger("Melshape.Goals")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# XP por concluir meta (usa config se disponível)
_XP_META_CONCLUIDA: int = getattr(config, "XP_META_CONCLUIDA", 200)
_XP_META_75: int = getattr(config, "XP_META_75", 50)

# Dias para cálculos
_DEFAULT_PROGRESS_DAYS: int = 30

# Status de meta
_STATUS_ACHIEVED: str = "achieved"
_STATUS_ON_TRACK: str = "on_track"
_STATUS_NEEDS_ATTENTION: str = "needs_attention"
_STATUS_AT_RISK: str = "at_risk"

# Thresholds de status
_THRESHOLD_ACHIEVED: int = 100
_THRESHOLD_ON_TRACK: int = 75
_THRESHOLD_AT_RISK_DAYS: int = 3
_THRESHOLD_AT_RISK_PCT: int = 50
_THRESHOLD_NEEDS_ATTENTION_DAYS: int = 7
_THRESHOLD_NEEDS_ATTENTION_PCT: int = 70
_THRESHOLD_NEEDS_ATTENTION_LOW: int = 50

# Meta de água diária (ml)
_DAILY_WATER_GOAL_ML: int = 2000


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO DE METAS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GoalTemplate:
    """
    Modelo de template de meta.
    
    Attributes:
        tipo: Tipo da meta (peso/habito/consistencia/agua/proteina/livre)
        titulo: Título da meta
        valor_alvo: Valor alvo (None se customizável)
        unidade: Unidade de medida
        custom: Se o valor é customizável pelo usuário
        descricao: Descrição opcional
    """
    tipo: str
    titulo: str
    valor_alvo: float | None
    unidade: str
    custom: bool = False
    descricao: str = ""
    
    @property
    def is_custom(self) -> bool:
        """Verifica se o valor é customizável."""
        return self.custom or self.valor_alvo is None
    
    @property
    def display_value(self) -> str:
        """Retorna valor para exibição."""
        if self.valor_alvo is None:
            return "Personalizado"
        return f"{self.valor_alvo:.0f} {self.unidade}"


@dataclass(frozen=True)
class GoalProgress:
    """
    Modelo de progresso de uma meta.
    
    Attributes:
        goal_id: ID da meta
        current_value: Valor atual
        target_value: Valor alvo
        percentage: Percentual de progresso (0-100)
        is_completed: Se a meta está concluída
        status: Status da meta (achieved/on_track/needs_attention/at_risk)
        display_label: Rótulo para exibição
        days_remaining: Dias restantes (se houver prazo)
        goal_title: Título da meta
        goal_type: Tipo da meta
    """
    goal_id: str
    current_value: float
    target_value: float
    percentage: int
    is_completed: bool
    status: str = "on_track"
    display_label: str = ""
    days_remaining: int | None = None
    goal_title: str = ""
    goal_type: str = ""
    
    @property
    def is_achieved(self) -> bool:
        """Verifica se a meta foi alcançada."""
        return self.is_completed or self.percentage >= _THRESHOLD_ACHIEVED
    
    @property
    def is_on_track(self) -> bool:
        """Verifica se a meta está no caminho certo."""
        return self.status == _STATUS_ON_TRACK
    
    @property
    def needs_attention(self) -> bool:
        """Verifica se a meta precisa de atenção."""
        return self.status == _STATUS_NEEDS_ATTENTION
    
    @property
    def is_at_risk(self) -> bool:
        """Verifica se a meta está em risco."""
        return self.status == _STATUS_AT_RISK
    
    @property
    def status_icon(self) -> str:
        """Retorna ícone do status."""
        icons = {
            _STATUS_ACHIEVED: "✅",
            _STATUS_ON_TRACK: "📈",
            _STATUS_NEEDS_ATTENTION: "⚡",
            _STATUS_AT_RISK: "⚠️",
        }
        return icons.get(self.status, "📊")
    
    @property
    def status_label(self) -> str:
        """Retorna rótulo do status."""
        labels = {
            _STATUS_ACHIEVED: "Concluída",
            _STATUS_ON_TRACK: "No caminho",
            _STATUS_NEEDS_ATTENTION: "Precisa atenção",
            _STATUS_AT_RISK: "Em risco",
        }
        return labels.get(self.status, self.status)
    
    @property
    def progress_bar_text(self) -> str:
        """Retorna texto para barra de progresso."""
        return f"{self.percentage}% • {self.display_label}"


@dataclass(frozen=True)
class GoalSummary:
    """
    Modelo de resumo das metas do paciente.
    
    Attributes:
        total: Total de metas
        active: Metas ativas (não concluídas)
        completed: Metas concluídas
        average_progress: Progresso médio das metas ativas (0-100)
        best_performing_type: Tipo de meta com melhor desempenho
        worst_performing_type: Tipo de meta com pior desempenho
    """
    total: int = 0
    active: int = 0
    completed: int = 0
    average_progress: float = 0.0
    best_performing_type: str | None = None
    worst_performing_type: str | None = None
    
    @property
    def completion_rate(self) -> float:
        """Calcula taxa de conclusão (0-100)."""
        if self.total == 0:
            return 0.0
        return round(self.completed / self.total * 100, 1)
    
    @property
    def has_goals(self) -> bool:
        """Verifica se há metas."""
        return self.total > 0
    
    @property
    def all_completed(self) -> bool:
        """Verifica se todas as metas foram concluídas."""
        return self.total > 0 and self.completed == self.total


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES — TEMPLATES E LABELS
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, list[GoalTemplate]] = {
    "peso": [
        GoalTemplate("peso", "Perder 5 kg", 5.0, "kg", descricao="Reduza 5kg do seu peso atual"),
        GoalTemplate("peso", "Perder 10 kg", 10.0, "kg", descricao="Reduza 10kg do seu peso atual"),
        GoalTemplate("peso", "Atingir peso ideal", None, "kg", custom=True, descricao="Defina seu peso objetivo"),
    ],
    "habito": [
        GoalTemplate("habito", "30 dias de hábito", 30.0, "dias", descricao="Mantenha um hábito por 30 dias"),
        GoalTemplate("habito", "Aderência de 90%", 90.0, "%", descricao="Atinga 90% de aderência"),
    ],
    "consistencia": [
        GoalTemplate("consistencia", "7 dias seguidos", 7.0, "dias", descricao="Check-in por 7 dias consecutivos"),
        GoalTemplate("consistencia", "30 dias seguidos", 30.0, "dias", descricao="Check-in por 30 dias consecutivos"),
        GoalTemplate("consistencia", "90 dias seguidos", 90.0, "dias", descricao="Check-in por 90 dias consecutivos"),
    ],
    "agua": [
        GoalTemplate("agua", "Beber 2L por 7 dias", 7.0, "dias", descricao="Atinga a meta de água por 7 dias"),
        GoalTemplate("agua", "Meta diária 30 dias", 30.0, "dias", descricao="Atinga a meta de água por 30 dias"),
    ],
    "proteina": [
        GoalTemplate("proteina", "Meta proteica 7 dias", 1.6, "g/kg", descricao="Atinga a meta de proteína por 7 dias"),
        GoalTemplate("proteina", "Meta proteica 30 dias", 1.6, "g/kg", descricao="Atinga a meta de proteína por 30 dias"),
    ],
    "livre": [
        GoalTemplate("livre", "Meta personalizada", 100.0, "%", custom=True, descricao="Defina sua própria meta"),
    ],
}

_TIPO_LABELS: dict[str, tuple[str, str]] = {
    "peso": ("⚖️", "Peso"),
    "habito": ("📋", "Hábito"),
    "consistencia": ("🔥", "Consistência"),
    "agua": ("💧", "Hidratação"),
    "proteina": ("🥩", "Proteína"),
    "livre": ("🎯", "Livre"),
}


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK CALCULATORS (quando goals_calculators não está disponível)
# ─────────────────────────────────────────────────────────────────────────────

def _fallback_calc_peso(db: Database, goal: dict[str, Any], target: float) -> dict[str, Any]:
    """Calcula progresso de meta de peso (fallback)."""
    try:
        weights = db.get_weights(90)
        
        if weights.empty or len(weights) < 2:
            return {"valor_atual": 0.0, "pct": 0}
        
        # Pega peso mais recente e mais antigo
        first_weight = float(weights.iloc[0]["weight"])
        last_weight = float(weights.iloc[-1]["weight"])
        
        # Calcula diferença
        diff = first_weight - last_weight  # Positivo = perdeu peso
        
        # Calcula progresso
        pct = min(100, int(abs(diff) / target * 100))
        
        return {"valor_atual": round(abs(diff), 1), "pct": pct}
    except Exception as e:
        logger.warning(f"_fallback_calc_peso falhou: {e}")
        return {"valor_atual": 0.0, "pct": 0}


def _fallback_calc_habito(db: Database, goal: dict[str, Any], target: float) -> dict[str, Any]:
    """Calcula progresso de meta de hábito (fallback)."""
    try:
        habits = db.get_habits()
        
        if not habits:
            return {"valor_atual": 0.0, "pct": 0}
        
        # Pega primeiro hábito
        habit_id = habits[0].id if hasattr(habits[0], "id") else habits[0].get("id", "")
        
        if not habit_id:
            return {"valor_atual": 0.0, "pct": 0}
        
        # Busca registros dos últimos 30 dias
        records = db.get_habit_records(habit_id, days=30)
        
        # Conta dias únicos
        unique_days = len(set(
            r.data_registro if hasattr(r, "data_registro") else r.get("data_registro", "")
            for r in records
        ))
        
        pct = min(100, int(unique_days / target * 100))
        
        return {"valor_atual": float(unique_days), "pct": pct}
    except Exception as e:
        logger.warning(f"_fallback_calc_habito falhou: {e}")
        return {"valor_atual": 0.0, "pct": 0}


def _fallback_calc_consistencia(db: Database, target: float) -> dict[str, Any]:
    """Calcula progresso de meta de consistência (fallback)."""
    try:
        streak = db.get_checkin_streak()
        pct = min(100, int(streak / target * 100))
        return {"valor_atual": float(streak), "pct": pct}
    except Exception as e:
        logger.warning(f"_fallback_calc_consistencia falhou: {e}")
        return {"valor_atual": 0.0, "pct": 0}


def _fallback_calc_agua(db: Database, target: float) -> dict[str, Any]:
    """Calcula progresso de meta de água (fallback)."""
    try:
        # Busca registros de hidratação dos últimos 30 dias
        # Como não temos método específico, retorna 0
        return {"valor_atual": 0.0, "pct": 0}
    except Exception as e:
        logger.warning(f"_fallback_calc_agua falhou: {e}")
        return {"valor_atual": 0.0, "pct": 0}


def _fallback_calc_proteina(db: Database, goal: dict[str, Any], target: float) -> dict[str, Any]:
    """Calcula progresso de meta de proteína (fallback)."""
    try:
        # Busca refeições dos últimos 7 dias
        meals = db.get_meals(7)
        
        if not meals:
            return {"valor_atual": 0.0, "pct": 0}
        
        # Calcula média de proteína por dia
        total_protein = sum(m.protein for m in meals)
        days = len(set(m.meal_date for m in meals))
        
        if days == 0:
            return {"valor_atual": 0.0, "pct": 0}
        
        avg_protein = total_protein / days
        
        # Converte para g/kg se tiver peso
        user = goal.get("user")
        if user:
            weight = user.get("current_weight") or user.get("peso_atual")
            if weight:
                avg_protein_per_kg = avg_protein / weight
                pct = min(100, int(avg_protein_per_kg / target * 100))
                return {"valor_atual": round(avg_protein_per_kg, 1), "pct": pct}
        
        pct = min(100, int(avg_protein / target * 100))
        return {"valor_atual": round(avg_protein, 1), "pct": pct}
    except Exception as e:
        logger.warning(f"_fallback_calc_proteina falhou: {e}")
        return {"valor_atual": 0.0, "pct": 0}


# ─────────────────────────────────────────────────────────────────────────────
# GOALS SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class GoalsService:
    """
    Serviço de metas: progresso automático, templates e conclusão.
    
    Example:
        >>> db = Database()
        >>> goals_service = GoalsService(db)
        >>> goals = goals_service.get_patient_goals(user)
        >>> for g in goals:
        ...     progress = goals_service.calculate_progress(g)
        ...     print(f"{g.titulo}: {progress.percentage}%")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de metas.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug(f"✅ GoalsService inicializado (calculators: {'sim' if _HAS_CALCULATORS else 'fallback'})")

    # ─────────────────────────────────────────────────────────────────────────
    # TEMPLATES
    # ─────────────────────────────────────────────────────────────────────────

    def templates(self) -> dict[str, list[GoalTemplate]]:
        """
        Retorna templates de metas por tipo.
        
        Returns:
            Dicionário com templates por tipo
            
        Example:
            >>> templates = goals_service.templates()
            >>> for t in templates["peso"]:
            ...     print(f"{t.titulo}: {t.display_value}")
        """
        return _TEMPLATES

    def tipo_labels(self) -> dict[str, tuple[str, str]]:
        """
        Retorna labels dos tipos de meta.
        
        Returns:
            Dicionário com (ícone, label) por tipo
            
        Example:
            >>> labels = goals_service.tipo_labels()
            >>> print(f"{labels['peso'][0]} {labels['peso'][1]}")
        """
        return _TIPO_LABELS

    def get_templates_by_type(self, tipo: str) -> list[GoalTemplate]:
        """
        Retorna templates de um tipo específico.
        
        Args:
            tipo: Tipo da meta (peso/habito/consistencia/agua/proteina/livre)
            
        Returns:
            Lista de templates do tipo
            
        Example:
            >>> templates = goals_service.get_templates_by_type("peso")
            >>> for t in templates:
            ...     print(t.titulo)
        """
        if not tipo:
            logger.warning("get_templates_by_type: tipo não informado")
            return []
        
        templates = _TEMPLATES.get(tipo, [])
        logger.debug(f"get_templates_by_type: {len(templates)} templates para {tipo}")
        return templates

    # ─────────────────────────────────────────────────────────────────────────
    # PROGRESSO
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_progress(self, goal: Goal | dict[str, Any]) -> GoalProgress:
        """
        Calcula progresso atual da meta com dados reais do banco.
        
        Args:
            goal: Objeto Goal ou dicionário
            
        Returns:
            Objeto GoalProgress com progresso calculado
            
        Example:
            >>> progress = goals_service.calculate_progress(goal)
            >>> print(f"Progresso: {progress.percentage}%")
            >>> print(f"Status: {progress.status_label}")
        """
        # Converte para dicionário se for objeto
        goal_data = self._ensure_goal_dict(goal)
        
        if not goal_data:
            logger.warning("calculate_progress: meta inválida")
            return self._empty_progress("")

        goal_id = goal_data.get("id", "")
        tipo = goal_data.get("tipo", "livre")
        valor_alvo = float(goal_data.get("valor_alvo") or 0)
        prazo = goal_data.get("prazo")
        titulo = goal_data.get("titulo", "")
        
        # Validações
        if valor_alvo <= 0 and tipo != "livre":
            logger.warning(f"calculate_progress: valor_alvo inválido para meta {goal_id}")
            return self._empty_progress(goal_id)

        try:
            # Calcula progresso baseado no tipo
            result = self._calculate_progress_by_type(tipo, goal_data, valor_alvo)
            
            # Calcula status
            status = self._calculate_goal_status(result, goal_data)
            
            # Dias restantes
            days_remaining = self.days_remaining(prazo) if prazo else None
            
            progress = GoalProgress(
                goal_id=goal_id,
                current_value=result["current_value"],
                target_value=valor_alvo,
                percentage=result["percentage"],
                is_completed=result["percentage"] >= _THRESHOLD_ACHIEVED,
                status=status,
                display_label=result["display_label"],
                days_remaining=days_remaining,
                goal_title=titulo,
                goal_type=tipo,
            )
            
            logger.debug(f"✅ Progresso calculado para {goal_id}: {progress.percentage}% ({status})")
            return progress

        except Exception as e:
            logger.error(f"calculate_progress falhou para {goal_id}: {e}")
            return self._empty_progress(goal_id)

    def _calculate_progress_by_type(
        self,
        tipo: str,
        goal_data: dict[str, Any],
        valor_alvo: float,
    ) -> dict[str, Any]:
        """
        Calcula progresso baseado no tipo da meta.
        
        Args:
            tipo: Tipo da meta
            goal_data: Dados da meta
            valor_alvo: Valor alvo
            
        Returns:
            Dicionário com current_value, percentage, display_label
        """
        if tipo == "peso":
            return self._calc_peso_progress(goal_data, valor_alvo)
        elif tipo == "habito":
            return self._calc_habito_progress(goal_data, valor_alvo)
        elif tipo == "consistencia":
            return self._calc_consistencia_progress(valor_alvo)
        elif tipo == "agua":
            return self._calc_agua_progress(valor_alvo)
        elif tipo == "proteina":
            return self._calc_proteina_progress(goal_data, valor_alvo)
        else:  # livre
            return self._calc_livre_progress(goal_data, valor_alvo)

    def _ensure_goal_dict(self, goal: Goal | dict[str, Any]) -> dict[str, Any]:
        """
        Converte Goal para dicionário se necessário.
        
        Args:
            goal: Objeto Goal ou dicionário
            
        Returns:
            Dicionário com dados da meta
        """
        if goal is None:
            return {}
        
        # Se já é dict, retorna
        if isinstance(goal, dict):
            return goal
        
        # Se é dataclass, usa asdict
        if dataclasses.is_dataclass(goal):
            return dataclasses.asdict(goal)
        
        # Fallback: tenta __dict__
        if hasattr(goal, "__dict__"):
            return goal.__dict__
        
        return {}

    def _empty_progress(self, goal_id: str) -> GoalProgress:
        """Retorna progresso vazio."""
        return GoalProgress(
            goal_id=goal_id,
            current_value=0.0,
            target_value=0.0,
            percentage=0,
            is_completed=False,
            display_label="0 de 0",
        )

    def _calc_peso_progress(self, goal: dict[str, Any], target: float) -> dict[str, Any]:
        """Calcula progresso de meta de peso."""
        if _HAS_CALCULATORS:
            result = calc_peso(self.db, goal, target)
        else:
            result = _fallback_calc_peso(self.db, goal, target)
        
        return {
            "current_value": result["valor_atual"],
            "percentage": result["pct"],
            "display_label": f"{result['valor_atual']:.1f} de {target:.1f} kg",
        }

    def _calc_habito_progress(self, goal: dict[str, Any], target: float) -> dict[str, Any]:
        """Calcula progresso de meta de hábito."""
        if _HAS_CALCULATORS:
            result = calc_habito(self.db, goal, target)
        else:
            result = _fallback_calc_habito(self.db, goal, target)
        
        unidade = goal.get("unidade", "dias")
        return {
            "current_value": result["valor_atual"],
            "percentage": result["pct"],
            "display_label": f"{result['valor_atual']:.0f} de {target:.0f} {unidade}",
        }

    def _calc_consistencia_progress(self, target: float) -> dict[str, Any]:
        """Calcula progresso de meta de consistência."""
        if _HAS_CALCULATORS:
            result = calc_consistencia(self.db, target)
        else:
            result = _fallback_calc_consistencia(self.db, target)
        
        return {
            "current_value": result["valor_atual"],
            "percentage": result["pct"],
            "display_label": f"{result['valor_atual']:.0f} de {target:.0f} dias seguidos",
        }

    def _calc_agua_progress(self, target: float) -> dict[str, Any]:
        """Calcula progresso de meta de água."""
        if _HAS_CALCULATORS:
            result = calc_agua(self.db, target)
        else:
            result = _fallback_calc_agua(self.db, target)
        
        return {
            "current_value": result["valor_atual"],
            "percentage": result["pct"],
            "display_label": f"{result['valor_atual']:.0f} de {target:.0f} dias com 2L",
        }

    def _calc_proteina_progress(self, goal: dict[str, Any], target: float) -> dict[str, Any]:
        """Calcula progresso de meta de proteína."""
        if _HAS_CALCULATORS:
            result = calc_proteina(self.db, goal, target)
        else:
            result = _fallback_calc_proteina(self.db, goal, target)
        
        return {
            "current_value": result["valor_atual"],
            "percentage": result["pct"],
            "display_label": f"{result['valor_atual']:.1f}g de {target:.1f}g/kg/dia",
        }

    def _calc_livre_progress(self, goal: dict[str, Any], target: float) -> dict[str, Any]:
        """Calcula progresso de meta livre (manual)."""
        current = float(goal.get("valor_atual") or 0)
        percentage = int(current / target * 100) if target > 0 else 0
        unidade = goal.get("unidade", "")
        
        return {
            "current_value": current,
            "percentage": min(100, percentage),
            "display_label": f"{current:.0f} de {target:.0f} {unidade}",
        }

    def _calculate_goal_status(
        self,
        result: dict[str, Any],
        goal: dict[str, Any],
    ) -> str:
        """
        Calcula o status da meta baseado no progresso e prazo.
        
        Args:
            result: Resultado do cálculo de progresso
            goal: Dicionário da meta
            
        Returns:
            Status da meta
        """
        percentage = result["percentage"]
        prazo = goal.get("prazo")
        
        # Meta concluída
        if percentage >= _THRESHOLD_ACHIEVED:
            return _STATUS_ACHIEVED
        
        # Meta acima de 75%
        if percentage >= _THRESHOLD_ON_TRACK:
            return _STATUS_ON_TRACK
        
        # Verifica prazo
        if prazo:
            days_remaining = self.days_remaining(prazo)
            if days_remaining is not None:
                if days_remaining <= _THRESHOLD_AT_RISK_DAYS and percentage < _THRESHOLD_AT_RISK_PCT:
                    return _STATUS_AT_RISK
                if days_remaining <= _THRESHOLD_NEEDS_ATTENTION_DAYS and percentage < _THRESHOLD_NEEDS_ATTENTION_PCT:
                    return _STATUS_NEEDS_ATTENTION
        
        # Meta abaixo de 50%
        if percentage < _THRESHOLD_NEEDS_ATTENTION_LOW:
            return _STATUS_NEEDS_ATTENTION
        
        return _STATUS_ON_TRACK

    # ─────────────────────────────────────────────────────────────────────────
    # CONCLUSÃO DE METAS
    # ─────────────────────────────────────────────────────────────────────────

    def complete_goal(self, goal_id: str) -> bool:
        """
        Marca uma meta como concluída e credita XP.
        
        Args:
            goal_id: ID da meta
            
        Returns:
            True se concluída com sucesso, False caso contrário
            
        Example:
            >>> success = goals_service.complete_goal("goal_123")
            >>> if success:
            ...     print("🏆 Meta concluída! +200 XP")
        """
        if not goal_id:
            logger.warning("complete_goal: goal_id não informado")
            return False
        
        try:
            # Busca a meta
            goal = self.get_goal_by_id(goal_id)
            
            if not goal:
                logger.warning(f"complete_goal: meta não encontrada: {goal_id}")
                return False
            
            # Verifica se já está concluída
            if goal.concluida:
                logger.debug(f"complete_goal: meta já concluída: {goal_id}")
                return False
            
            # Atualiza no banco
            success = self.db.update_goal(goal_id, {"concluida": True, "concluida_em": date.today().isoformat()})
            
            if not success:
                logger.error(f"complete_goal: falha ao atualizar meta {goal_id}")
                return False
            
            # Credita XP
            self.db.add_xp(_XP_META_CONCLUIDA, motivo=f"meta_concluida_{goal_id[:8]}")
            
            logger.info(f"✅ Meta concluída: {goal.titulo} (+{_XP_META_CONCLUIDA} XP)")
            return True
            
        except Exception as e:
            logger.error(f"complete_goal falhou para {goal_id}: {e}")
            return False

    def is_goal_achievable(self, goal: Goal | dict[str, Any]) -> bool:
        """
        Verifica se uma meta é alcançável (não impossível).
        
        Args:
            goal: Objeto Goal ou dicionário
            
        Returns:
            True se alcançável, False caso contrário
            
        Example:
            >>> if goals_service.is_goal_achievable(goal):
            ...     print("Meta alcançável!")
        """
        goal_data = self._ensure_goal_dict(goal)
        
        if not goal_data:
            return False
        
        target = float(goal_data.get("valor_alvo") or 0)
        
        # Meta com alvo 0 ou negativo é inválida
        if target <= 0:
            return False
        
        # Verifica se há dados para calcular progresso
        try:
            progress = self.calculate_progress(goal)
            
            # Se já está concluída, é alcançável
            if progress.is_completed:
                return True
            
            # Se há prazo e está em risco, ainda pode ser alcançável
            if progress.is_at_risk:
                # Verifica se há pelo menos 30% de progresso
                return progress.percentage >= 30
            
            return True
            
        except Exception as e:
            logger.warning(f"is_goal_achievable falhou: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # METAS DO PACIENTE
    # ─────────────────────────────────────────────────────────────────────────

    def get_goal_by_id(self, goal_id: str) -> Goal | None:
        """
        Busca uma meta pelo ID.
        
        Args:
            goal_id: ID da meta
            
        Returns:
            Objeto Goal ou None se não encontrado
            
        Example:
            >>> goal = goals_service.get_goal_by_id("goal_123")
            >>> if goal:
            ...     print(f"Meta: {goal.titulo}")
        """
        if not goal_id:
            logger.warning("get_goal_by_id: goal_id não informado")
            return None
        
        try:
            # Busca jornada ativa
            journey = self.db.get_journey_ativa()
            if not journey:
                logger.debug("get_goal_by_id: nenhuma jornada ativa")
                return None
            
            journey_id = journey.id if hasattr(journey, "id") else journey.get("id", "")
            
            # Busca metas
            goals = self.db.get_metas(journey_id)
            
            # Busca meta específica
            for g in goals:
                g_id = g.id if hasattr(g, "id") else g.get("id", "")
                if g_id == goal_id:
                    # Converte para Goal se necessário
                    if isinstance(g, Goal):
                        return g
                    return Goal.from_dict(g)
            
            logger.debug(f"get_goal_by_id: meta não encontrada: {goal_id}")
            return None
            
        except Exception as e:
            logger.error(f"get_goal_by_id falhou: {e}")
            return None

    def get_patient_goals(self, user: dict[str, Any] | Any) -> list[Goal]:
        """
        Retorna todas as metas do paciente.
        
        Args:
            user: Objeto User ou dicionário (não usado, busca por jornada ativa)
            
        Returns:
            Lista de objetos Goal
            
        Example:
            >>> goals = goals_service.get_patient_goals(user)
            >>> for g in goals:
            ...     print(f"{g.titulo}: {g.valor_atual}/{g.valor_alvo}")
        """
        try:
            # Busca jornada ativa
            journey = self.db.get_journey_ativa()
            if not journey:
                logger.debug("get_patient_goals: nenhuma jornada ativa")
                return []
            
            journey_id = journey.id if hasattr(journey, "id") else journey.get("id", "")
            
            # Busca metas
            goals = self.db.get_metas(journey_id)
            
            # Converte para objetos Goal se necessário
            result = []
            for g in goals:
                if isinstance(g, Goal):
                    result.append(g)
                else:
                    result.append(Goal.from_dict(g))
            
            logger.debug(f"✅ {len(result)} metas encontradas")
            return result
            
        except Exception as e:
            logger.error(f"get_patient_goals falhou: {e}")
            return []

    def get_active_goals(self, user: dict[str, Any] | Any) -> list[Goal]:
        """
        Retorna metas ativas (não concluídas) do paciente.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Lista de objetos Goal ativos
            
        Example:
            >>> active = goals_service.get_active_goals(user)
            >>> for g in active:
            ...     print(f"🎯 {g.titulo}")
        """
        goals = self.get_patient_goals(user)
        
        active = [g for g in goals if not g.concluida]
        
        logger.debug(f"✅ {len(active)} metas ativas")
        return active

    def get_completed_goals(self, user: dict[str, Any] | Any) -> list[Goal]:
        """
        Retorna metas concluídas do paciente.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Lista de objetos Goal concluídos
            
        Example:
            >>> completed = goals_service.get_completed_goals(user)
            >>> for g in completed:
            ...     print(f"🏆 {g.titulo}")
        """
        goals = self.get_patient_goals(user)
        
        completed = [g for g in goals if g.concluida]
        
        logger.debug(f"✅ {len(completed)} metas concluídas")
        return completed

    def get_goal_summary(self, user: dict[str, Any] | Any) -> GoalSummary:
        """
        Retorna resumo das metas do paciente.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Objeto GoalSummary com resumo completo
            
        Example:
            >>> summary = goals_service.get_goal_summary(user)
            >>> print(f"Total: {summary.total}, Ativas: {summary.active}, Concluídas: {summary.completed}")
            >>> print(f"Taxa de conclusão: {summary.completion_rate}%")
        """
        goals = self.get_patient_goals(user)
        
        if not goals:
            return GoalSummary()
        
        total = len(goals)
        completed = 0
        progress_sum = 0.0
        active_count = 0
        
        type_progress: dict[str, list[float]] = {}
        
        for g in goals:
            if g.concluida:
                completed += 1
            else:
                active_count += 1
                # Calcula progresso
                prog = self.calculate_progress(g)
                progress_sum += prog.percentage
                
                # Agrupa por tipo
                tipo = g.tipo
                if tipo not in type_progress:
                    type_progress[tipo] = []
                type_progress[tipo].append(prog.percentage)
        
        # Calcula média de progresso
        avg_progress = round(progress_sum / active_count, 1) if active_count > 0 else 0.0
        
        # Encontra melhor e pior tipo
        best_type = None
        worst_type = None
        best_avg = 0.0
        worst_avg = 100.0
        
        for tipo, progress_list in type_progress.items():
            if progress_list:
                avg = sum(progress_list) / len(progress_list)
                if avg > best_avg:
                    best_avg = avg
                    best_type = tipo
                if avg < worst_avg:
                    worst_avg = avg
                    worst_type = tipo
        
        summary = GoalSummary(
            total=total,
            active=active_count,
            completed=completed,
            average_progress=avg_progress,
            best_performing_type=best_type,
            worst_performing_type=worst_type,
        )
        
        logger.debug(f"✅ Resumo de metas: {summary.total} total, {summary.completed} concluídas")
        return summary

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITÁRIOS
    # ─────────────────────────────────────────────────────────────────────────

    def days_remaining(self, prazo: str | None) -> int | None:
        """
        Calcula dias restantes até o prazo.
        
        Args:
            prazo: Data no formato YYYY-MM-DD
            
        Returns:
            Número de dias restantes ou None
            
        Example:
            >>> days = goals_service.days_remaining("2026-12-31")
            >>> print(f"Dias restantes: {days}")
        """
        if not prazo:
            return None
        
        try:
            target_date = date.fromisoformat(prazo[:10])
            remaining = (target_date - date.today()).days
            return max(0, remaining)
        except Exception as e:
            logger.debug(f"days_remaining falhou para {prazo}: {e}")
            return None

    def goal_status(self, goal: Goal | dict[str, Any]) -> str:
        """
        Retorna o status da meta como string legível.
        
        Args:
            goal: Objeto Goal ou dicionário
            
        Returns:
            Status da meta
            
        Example:
            >>> status = goals_service.goal_status(goal)
            >>> print(f"Status: {status}")
        """
        progress = self.calculate_progress(goal)
        return progress.status_label

    def get_best_goal_type(self, user: dict[str, Any] | Any) -> str | None:
        """
        Retorna o tipo de meta com melhor desempenho.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Tipo da meta com melhor progresso ou None
            
        Example:
            >>> best = goals_service.get_best_goal_type(user)
            >>> print(f"Melhor tipo: {best}")
        """
        goals = self.get_patient_goals(user)
        
        if not goals:
            return None
        
        best_type = None
        best_progress = 0
        
        for g in goals:
            progress = self.calculate_progress(g)
            if progress.percentage > best_progress and progress.percentage < 100:
                best_progress = progress.percentage
                best_type = g.tipo
        
        return best_type

    def get_goals_with_progress(self, user: dict[str, Any] | Any) -> list[tuple[Goal, GoalProgress]]:
        """
        Retorna metas com progresso calculado.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Lista de tuplas (Goal, GoalProgress)
            
        Example:
            >>> goals_with_progress = goals_service.get_goals_with_progress(user)
            >>> for goal, progress in goals_with_progress:
            ...     print(f"{goal.titulo}: {progress.percentage}%")
        """
        goals = self.get_patient_goals(user)
        
        result = []
        for g in goals:
            progress = self.calculate_progress(g)
            result.append((g, progress))
        
        # Ordena por progresso (maior primeiro)
        result.sort(key=lambda x: x[1].percentage, reverse=True)
        
        return result


__all__ = [
    "GoalsService",
    "GoalProgress",
    "GoalTemplate",
    "GoalSummary",
]
