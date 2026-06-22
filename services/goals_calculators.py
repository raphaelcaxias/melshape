"""
Melshape — Goals Calculators.

Funções puras para cálculo de progresso de metas.
Importadas por GoalsService.

Cada função recebe db e parâmetros da meta, e retorna um dicionário
com valor_atual, pct, concluida e delta_label.

Princípios:
- Funções puras: sem efeitos colaterais
- Fallback automático: trata dados ausentes
- Tipagem forte: todos os parâmetros são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas

Tipos de meta suportados:
    - peso: progresso baseado em pesagens (redução ou ganho)
    - habito: progresso baseado em dias com hábitos registrados
    - consistencia: progresso baseado em streak de check-ins
    - agua: progresso baseado em dias com meta de água atingida
    - proteina: progresso baseado em média de proteína (7d)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger("Melshape.GoalsCalculators")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Meta de água diária (ml)
_WATER_GOAL_ML: int = 2000

# Dias para cálculo de proteína
_PROTEIN_DAYS: int = 7

# Dias para cálculo de água
_WATER_DAYS: int = 30

# Dias para cálculo de peso
_WEIGHT_DAYS: int = 365

# Dias para cálculo de hábito
_HABIT_DAYS: int = 365

# Dias para cálculo de consistência
_CONSISTENCIA_DAYS: int = 365


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _zero_progress(meta: dict[str, Any], target: float) -> dict[str, Any]:
    """Retorna progresso vazio."""
    return {
        "valor_atual": 0.0,
        "pct": 0,
        "concluida": False,
        "delta_label": f"0 de {target:.0f} {meta.get('unidade', '')}",
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Converte valor para float de forma segura."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# CALCULATORS
# ─────────────────────────────────────────────────────────────────────────────

def calc_peso(db: Any, meta: dict[str, Any], target: float) -> dict[str, Any]:
    """
    Calcula progresso de meta de peso.
    
    Args:
        db: Instância do Database
        meta: Dicionário com dados da meta
        target: Valor alvo
    
    Returns:
        Dicionário com valor_atual, pct, concluida, delta_label
    """
    if target <= 0:
        return _zero_progress(meta, target)

    try:
        weights = db.get_weights(days=_WEIGHT_DAYS)
        
        if weights.empty or len(weights) < 2:
            return _zero_progress(meta, target)
        
        # Primeiro e último peso
        first_weight = _safe_float(weights.iloc[0]["weight"])
        last_weight = _safe_float(weights.iloc[-1]["weight"])
        
        if first_weight <= 0 or last_weight <= 0:
            return _zero_progress(meta, target)
        
        # Calcula diferença (perda de peso = positivo)
        diff = first_weight - last_weight
        current = abs(diff)
        pct = min(100, int(current / target * 100))
        
        return {
            "valor_atual": round(current, 1),
            "pct": pct,
            "concluida": pct >= 100,
            "delta_label": f"{current:.1f} de {target:.1f} kg ({pct}%)",
        }
        
    except Exception as e:
        logger.warning(f"calc_peso: {e}")
        return _zero_progress(meta, target)


def calc_habito(db: Any, meta: dict[str, Any], target: float) -> dict[str, Any]:
    """
    Calcula progresso de meta de hábito.
    
    Args:
        db: Instância do Database
        meta: Dicionário com dados da meta
        target: Valor alvo
    
    Returns:
        Dicionário com valor_atual, pct, concluida, delta_label
    """
    if target <= 0:
        return _zero_progress(meta, target)

    try:
        habits = db.get_habits()
        
        if not habits:
            return _zero_progress(meta, target)
        
        unidade = meta.get("unidade", "dias")
        
        if unidade == "%":
            # Aderência em %
            from services.habit_service import HabitService
            actual = HabitService(db).overall_adherence(days=30)
            pct = min(100, int(actual))
            return {
                "valor_atual": round(actual, 1),
                "pct": pct,
                "concluida": pct >= 100,
                "delta_label": f"{actual:.0f}% de {target:.0f}%",
            }
        
        # Dias com hábito registrado
        done_days: set[str] = set()
        for habit in habits:
            habit_id = habit.id if hasattr(habit, "id") else habit.get("id", "")
            if habit_id:
                records = db.get_habit_records(habit_id, days=_HABIT_DAYS)
                for record in records:
                    date_str = record.data_registro if hasattr(record, "data_registro") else record.get("data_registro", "")
                    if date_str:
                        done_days.add(date_str)
        
        current = float(len(done_days))
        pct = min(100, int(current / target * 100))
        
        return {
            "valor_atual": current,
            "pct": pct,
            "concluida": pct >= 100,
            "delta_label": f"{current:.0f} de {target:.0f} {unidade}",
        }
        
    except Exception as e:
        logger.warning(f"calc_habito: {e}")
        return _zero_progress(meta, target)


def calc_consistencia(db: Any, target: float) -> dict[str, Any]:
    """
    Calcula progresso de meta de consistência (streak).
    
    Args:
        db: Instância do Database
        target: Valor alvo
    
    Returns:
        Dicionário com valor_atual, pct, concluida, delta_label
    """
    if target <= 0:
        return {
            "valor_atual": 0.0,
            "pct": 0,
            "concluida": False,
            "delta_label": f"0 de {target:.0f} dias seguidos",
        }

    try:
        streak = db.get_checkin_streak()
        current = float(streak)
        pct = min(100, int(current / target * 100))
        
        return {
            "valor_atual": current,
            "pct": pct,
            "concluida": pct >= 100,
            "delta_label": f"{streak} de {target:.0f} dias seguidos",
        }
        
    except Exception as e:
        logger.warning(f"calc_consistencia: {e}")
        return {
            "valor_atual": 0.0,
            "pct": 0,
            "concluida": False,
            "delta_label": f"0 de {target:.0f} dias seguidos",
        }


def calc_agua(db: Any, target: float) -> dict[str, Any]:
    """
    Calcula progresso de meta de água.
    
    Args:
        db: Instância do Database
        target: Valor alvo (dias com meta de água atingida)
    
    Returns:
        Dicionário com valor_atual, pct, concluida, delta_label
    """
    if target <= 0:
        return {
            "valor_atual": 0.0,
            "pct": 0,
            "concluida": False,
            "delta_label": f"0 de {target:.0f} dias com 2L",
        }

    try:
        uid = db.uid()
        days_ok = 0
        
        for i in range(_WATER_DAYS):
            date_str = (date.today() - timedelta(days=i)).isoformat()
            total = 0
            
            # Tenta Supabase primeiro
            if db.is_real and db.client:
                try:
                    response = (db.client.table("registros_agua")
                                .select("quantidade_ml")
                                .eq("perfil_id", uid)
                                .eq("data_registro", date_str)
                                .execute())
                    total = sum(_safe_float(x.get("quantidade_ml", 0)) for x in (response.data or []))
                except Exception:
                    # Fallback para mock
                    total = sum(
                        _safe_float(x.get("amount_ml", 0))
                        for x in db._mock().get("hydration", [])
                        if x.get("user_id") == uid and x.get("log_date") == date_str
                    )
            else:
                # MockDB
                total = sum(
                    _safe_float(x.get("amount_ml", 0))
                    for x in db._mock().get("hydration", [])
                    if x.get("user_id") == uid and x.get("log_date") == date_str
                )
            
            if total >= _WATER_GOAL_ML:
                days_ok += 1
        
        current = float(days_ok)
        pct = min(100, int(current / target * 100))
        
        return {
            "valor_atual": current,
            "pct": pct,
            "concluida": pct >= 100,
            "delta_label": f"{days_ok} de {target:.0f} dias com 2L",
        }
        
    except Exception as e:
        logger.warning(f"calc_agua: {e}")
        return {
            "valor_atual": 0.0,
            "pct": 0,
            "concluida": False,
            "delta_label": f"0 de {target:.0f} dias com 2L",
        }


def calc_proteina(db: Any, meta: dict[str, Any], target: float) -> dict[str, Any]:
    """
    Calcula progresso de meta de proteína.
    
    Args:
        db: Instância do Database
        meta: Dicionário com dados da meta
        target: Valor alvo (g/kg)
    
    Returns:
        Dicionário com valor_atual, pct, concluida, delta_label
    """
    if target <= 0:
        return {
            "valor_atual": 0.0,
            "pct": 0,
            "concluida": False,
            "delta_label": f"0g de {target:.1f}g/kg/dia",
        }

    try:
        meals = db.get_meals(days=_PROTEIN_DAYS)
        
        if not meals:
            return {
                "valor_atual": 0.0,
                "pct": 0,
                "concluida": False,
                "delta_label": f"0g de {target:.1f}g/kg/dia",
            }
        
        # Calcula proteína média por dia
        from collections import defaultdict
        protein_by_day: dict[str, float] = defaultdict(float)
        for meal in meals:
            protein = meal.protein if hasattr(meal, "protein") else meal.get("protein", 0)
            protein_by_day[meal.meal_date] += _safe_float(protein)
        
        if not protein_by_day:
            return {
                "valor_atual": 0.0,
                "pct": 0,
                "concluida": False,
                "delta_label": f"0g de {target:.1f}g/kg/dia",
            }
        
        avg_protein = sum(protein_by_day.values()) / len(protein_by_day)
        
        # Converte para g/kg se tiver peso
        if avg_protein > 0:
            # Busca peso do usuário
            user = meta.get("user")
            if user:
                weight = _safe_float(user.get("current_weight") or user.get("peso_atual"))
                if weight > 0:
                    avg_protein_per_kg = avg_protein / weight
                    pct = min(100, int(avg_protein_per_kg / target * 100))
                    return {
                        "valor_atual": round(avg_protein_per_kg, 1),
                        "pct": pct,
                        "concluida": pct >= 100,
                        "delta_label": f"{avg_protein_per_kg:.1f}g de {target:.1f}g/kg/dia",
                    }
        
        # Fallback: usa proteína absoluta
        pct = min(100, int(avg_protein / target * 100))
        return {
            "valor_atual": round(avg_protein, 1),
            "pct": pct,
            "concluida": pct >= 100,
            "delta_label": f"{avg_protein:.0f}g de {target:.1f}g/dia (média 7d)",
        }
        
    except Exception as e:
        logger.warning(f"calc_proteina: {e}")
        return {
            "valor_atual": 0.0,
            "pct": 0,
            "concluida": False,
            "delta_label": f"0g de {target:.1f}g/kg/dia",
        }


__all__ = [
    "calc_peso",
    "calc_habito",
    "calc_consistencia",
    "calc_agua",
    "calc_proteina",
]
