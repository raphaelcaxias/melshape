"""
Melshape — Goals Calculators.

Funções puras para cálculo de progresso de metas.
Importadas por GoalsService.

Cada função recebe db, meta e target, e retorna um ProgressResult
com valor_atual, pct, concluida e delta_label.

Princípios:
- Funções puras: sem efeitos colaterais
- Fallback automático: trata dados ausentes
- Tipagem forte: Protocol para DB, TypedDict para retorno (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- DRY: decorator @safe_calc elimina duplicação de try/except

Tipos de meta suportados:
    - peso: progresso baseado em pesagens (redução ou ganho)
    - habito: progresso baseado em dias com hábitos registrados
    - consistencia: progresso baseado em streak de check-ins
    - agua: progresso baseado em dias com meta de água atingida
    - proteina: progresso baseado em média de proteína (7d)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from functools import wraps
from typing import Any, Callable, Protocol, TypedDict, TypeVar, cast, runtime_checkable

logger = logging.getLogger("Melshape.GoalsCalculators")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

_WATER_GOAL_ML: int = 2000
_PROTEIN_DAYS: int = 7
_WATER_DAYS: int = 30
_WEIGHT_DAYS: int = 365
_HABIT_DAYS: int = 365
_DEFAULT_HABIT_UNIT: str = "dias"


# ─────────────────────────────────────────────────────────────────────────────
# TIPOS
# ─────────────────────────────────────────────────────────────────────────────

class ProgressResult(TypedDict):
    """Resultado padronizado de cálculo de progresso."""
    valor_atual: float
    pct: int
    concluida: bool
    delta_label: str


@runtime_checkable
class Database(Protocol):
    """Protocol para interface do banco de dados."""
    
    def uid(self) -> str: ...
    
    @property
    def is_real(self) -> bool: ...
    
    @property
    def client(self) -> Any: ...
    
    def get_weights(self, days: int) -> Any: ...
    def get_habits(self) -> list[Any]: ...
    def get_habit_records(self, habit_id: str, days: int) -> list[Any]: ...
    def get_checkin_streak(self) -> int: ...
    def get_meals(self, days: int) -> list[Any]: ...
    def get_hydration_logs(self, days: int) -> list[dict[str, Any]]: ...


# Tipo genérico para funções de cálculo
CalcFn = TypeVar("CalcFn", bound=Callable[..., ProgressResult])


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Converte valor para float de forma segura."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def _get_attr_or_key(obj: Any, attr: str, default: Any = None) -> Any:
    """Obtém atributo ou chave de dict de forma segura."""
    if hasattr(obj, attr):
        return getattr(obj, attr)
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return default


def _build_progress(
    valor_atual: float,
    target: float,
    unidade: str,
    concluida: bool | None = None,
    label_template: str | None = None,
) -> ProgressResult:
    """Constrói ProgressResult padronizado."""
    if target <= 0:
        pct = 0
    else:
        pct = min(100, int((valor_atual / target) * 100))
    
    is_complete = concluida if concluida is not None else (pct >= 100)
    
    if label_template:
        delta_label = label_template.format(
            valor=valor_atual,
            target=target,
            pct=pct,
            unidade=unidade,
        )
    else:
        delta_label = f"{valor_atual:.1f} de {target:.1f} {unidade} ({pct}%)"
    
    return ProgressResult(
        valor_atual=round(valor_atual, 2),
        pct=pct,
        concluida=is_complete,
        delta_label=delta_label,
    )


def _zero_progress(target: float, unidade: str, label: str | None = None) -> ProgressResult:
    """Retorna progresso zerado."""
    return ProgressResult(
        valor_atual=0.0,
        pct=0,
        concluida=False,
        delta_label=label or f"0 de {target:.1f} {unidade}",
    )


def safe_calc(
    fallback_factory: Callable[[float, str], ProgressResult],
) -> Callable[[CalcFn], CalcFn]:
    """
    Decorator para tratamento seguro de erros em calculadoras.
    
    Args:
        fallback_factory: Função que recebe (target, unidade) e retorna ProgressResult de fallback
    
    Returns:
        Decorator que encapsula try/except e logging
    """
    def decorator(fn: CalcFn) -> CalcFn:
        @wraps(fn)
        def wrapper(db: Database, meta: dict[str, Any], target: float, *args: Any, **kwargs: Any) -> ProgressResult:
            target = _safe_float(target)
            if target <= 0:
                logger.warning(f"{fn.__name__}: target inválido ({target})")
                unidade = meta.get("unidade", "") if meta else ""
                return fallback_factory(target, unidade)
            
            try:
                return fn(db, meta, target, *args, **kwargs)
            except Exception as e:
                logger.warning(f"{fn.__name__}: {e}")
                unidade = meta.get("unidade", "") if meta else ""
                return fallback_factory(target, unidade)
        
        return cast(CalcFn, wrapper)
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK FACTORIES
# ─────────────────────────────────────────────────────────────────────────────

def _fallback_peso(target: float, unidade: str) -> ProgressResult:
    return _zero_progress(target, "kg", f"0 de {target:.1f} kg")


def _fallback_habito(target: float, unidade: str) -> ProgressResult:
    un = unidade or _DEFAULT_HABIT_UNIT
    if un == "%":
        return _zero_progress(target, "%", f"0% de {target:.0f}%")
    return _zero_progress(target, un, f"0 de {target:.0f} {un}")


def _fallback_consistencia(target: float, unidade: str) -> ProgressResult:
    return _zero_progress(target, "dias", f"0 de {target:.0f} dias seguidos")


def _fallback_agua(target: float, unidade: str) -> ProgressResult:
    return _zero_progress(target, "dias", f"0 de {target:.0f} dias com 2L")


def _fallback_proteina(target: float, unidade: str) -> ProgressResult:
    return _zero_progress(target, "g/kg/dia", f"0g de {target:.1f}g/kg/dia")


# ─────────────────────────────────────────────────────────────────────────────
# CALCULATORS
# ─────────────────────────────────────────────────────────────────────────────

@safe_calc(_fallback_peso)
def calc_peso(db: Database, meta: dict[str, Any], target: float) -> ProgressResult:
    """
    Calcula progresso de meta de peso.
    
    Progresso = |peso_inicial - peso_final|
    Funciona tanto para perda quanto para ganho de peso.
    """
    weights = db.get_weights(days=_WEIGHT_DAYS)
    
    if weights.empty if hasattr(weights, "empty") else len(weights) < 2:
        return _fallback_peso(target, "kg")
    
    first_weight = _safe_float(weights.iloc[0]["weight"])
    last_weight = _safe_float(weights.iloc[-1]["weight"])
    
    if first_weight <= 0 or last_weight <= 0:
        return _fallback_peso(target, "kg")
    
    current = abs(first_weight - last_weight)
    
    return _build_progress(
        valor_atual=current,
        target=target,
        unidade="kg",
        label_template=f"{{valor:.1f}} de {{target:.1f}} kg ({{pct}}%)",
    )


@safe_calc(_fallback_habito)
def calc_habito(db: Database, meta: dict[str, Any], target: float) -> ProgressResult:
    """
    Calcula progresso de meta de hábito.
    
    Suporta dois modos:
    - unidade="%": aderência percentual (últimos 30 dias)
    - unidade="dias" (padrão): dias únicos com hábito registrado
    """
    habits = db.get_habits()
    if not habits:
        return _fallback_habito(target, meta.get("unidade", _DEFAULT_HABIT_UNIT))
    
    unidade = meta.get("unidade", _DEFAULT_HABIT_UNIT)
    
    # Modo percentual: delega para HabitService
    if unidade == "%":
        from services.habit_service import HabitService
        actual = HabitService(db).overall_adherence(days=30)
        return _build_progress(
            valor_atual=actual,
            target=target,
            unidade="%",
            label_template=f"{{valor:.0f}}% de {{target:.0f}}%",
        )
    
    # Modo dias: conta dias únicos com qualquer hábito registrado
    done_days: set[str] = set()
    for habit in habits:
        habit_id = _get_attr_or_key(habit, "id", "")
        if not habit_id:
            continue
        
        records = db.get_habit_records(habit_id, days=_HABIT_DAYS)
        for record in records:
            date_str = _get_attr_or_key(record, "data_registro", "")
            if date_str:
                done_days.add(date_str)
    
    return _build_progress(
        valor_atual=float(len(done_days)),
        target=target,
        unidade=unidade,
        label_template=f"{{valor:.0f}} de {{target:.0f}} {{unidade}}",
    )


@safe_calc(_fallback_consistencia)
def calc_consistencia(db: Database, meta: dict[str, Any], target: float) -> ProgressResult:
    """Calcula progresso de meta de consistência (streak de check-ins)."""
    streak = db.get_checkin_streak()
    current = float(streak)
    
    return _build_progress(
        valor_atual=current,
        target=target,
        unidade="dias",
        label_template=f"{{valor:.0f}} de {{target:.0f}} dias seguidos",
    )


@safe_calc(_fallback_agua)
def calc_agua(db: Database, meta: dict[str, Any], target: float) -> ProgressResult:
    """
    Calcula progresso de meta de água.
    
    Conta quantos dias (nos últimos 30) atingiram a meta de 2L.
    Usa query única ao invés de N queries (uma por dia).
    """
    # Query única: busca todos os logs dos últimos N dias
    try:
        logs = db.get_hydration_logs(days=_WATER_DAYS)
    except AttributeError:
        # Fallback para DBs antigos sem get_hydration_logs
        logs = _fetch_hydration_legacy(db, _WATER_DAYS)
    
    # Agrupa por data e soma volume
    volume_by_day: dict[str, float] = defaultdict(float)
    for log in logs:
        log_date = _get_attr_or_key(log, "data_registro") or _get_attr_or_key(log, "log_date", "")
        amount = _safe_float(
            _get_attr_or_key(log, "quantidade_ml") or _get_attr_or_key(log, "amount_ml", 0)
        )
        if log_date:
            volume_by_day[log_date] += amount
    
    # Conta dias que atingiram a meta
    days_ok = sum(1 for total in volume_by_day.values() if total >= _WATER_GOAL_ML)
    
    return _build_progress(
        valor_atual=float(days_ok),
        target=target,
        unidade="dias",
        label_template=f"{{valor:.0f}} de {{target:.0f}} dias com 2L",
    )


def _fetch_hydration_legacy(db: Database, days: int) -> list[dict[str, Any]]:
    """Fallback para DBs sem get_hydration_logs — compatibilidade retroativa."""
    uid = db.uid()
    logs: list[dict[str, Any]] = []
    
    # Tenta Supabase real
    if getattr(db, "is_real", False) and getattr(db, "client", None):
        try:
            start_date = (date.today() - timedelta(days=days)).isoformat()
            response = (
                db.client.table("registros_agua")
                .select("quantidade_ml,data_registro")
                .eq("perfil_id", uid)
                .gte("data_registro", start_date)
                .execute()
            )
            return list(response.data or [])
        except Exception as e:
            logger.warning(f"_fetch_hydration_legacy (supabase): {e}")
    
    # Fallback para mock
    try:
        mock_data = db._mock().get("hydration", [])  # type: ignore[attr-defined]
        return [
            x for x in mock_data
            if x.get("user_id") == uid
        ]
    except Exception as e:
        logger.warning(f"_fetch_hydration_legacy (mock): {e}")
        return []


@safe_calc(_fallback_proteina)
def calc_proteina(db: Database, meta: dict[str, Any], target: float) -> ProgressResult:
    """
    Calcula progresso de meta de proteína.
    
    Usa média dos últimos 7 dias.
    Se tiver peso do usuário, converte para g/kg/dia.
    Caso contrário, usa proteína absoluta (g/dia).
    """
    meals = db.get_meals(days=_PROTEIN_DAYS)
    if not meals:
        return _fallback_proteina(target, "g/kg/dia")
    
    # Agrupa proteína por dia
    protein_by_day: dict[str, float] = defaultdict(float)
    for meal in meals:
        meal_date = _get_attr_or_key(meal, "meal_date", "")
        protein = _safe_float(_get_attr_or_key(meal, "protein", 0))
        if meal_date:
            protein_by_day[meal_date] += protein
    
    if not protein_by_day:
        return _fallback_proteina(target, "g/kg/dia")
    
    avg_protein = sum(protein_by_day.values()) / len(protein_by_day)
    
    # Tenta converter para g/kg/dia
    user = meta.get("user") if meta else None
    if user:
        weight = _safe_float(
            user.get("current_weight") or user.get("peso_atual")
        )
        if weight > 0:
            avg_per_kg = avg_protein / weight
            return _build_progress(
                valor_atual=avg_per_kg,
                target=target,
                unidade="g/kg/dia",
                label_template=f"{{valor:.1f}}g de {{target:.1f}}g/kg/dia",
            )
    
    # Fallback: proteína absoluta
    return _build_progress(
        valor_atual=avg_protein,
        target=target,
        unidade="g/dia",
        label_template=f"{{valor:.0f}}g de {{target:.1f}}g/dia (média 7d)",
    )


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

CALCULATORS: dict[str, Callable[..., ProgressResult]] = {
    "peso": calc_peso,
    "habito": calc_habito,
    "consistencia": calc_consistencia,
    "agua": calc_agua,
    "proteina": calc_proteina,
}


def get_calculator(goal_type: str) -> Callable[..., ProgressResult] | None:
    """Obtém a função calculadora para um tipo de meta."""
    return CALCULATORS.get(goal_type)


__all__ = [
    # Calculators
    "calc_peso",
    "calc_habito",
    "calc_consistencia",
    "calc_agua",
    "calc_proteina",
    # Registry
    "CALCULATORS",
    "get_calculator",
    # Types
    "ProgressResult",
    "Database",
]
