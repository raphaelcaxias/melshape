"""
Melshape — Utilitários de Streak (módulo canônico).

Consolidação das 3 implementações distintas identificadas na Auditoria Mestra:
  - services/habit_service.py  (_calculate_streak_from_dates)
  - services/relapse_service.py (_calculate_best_streak)
  - services/gamification_service.py (_calculate_meal_streak — lógica diferente)

Constituição Cap. IX: "É proibido duplicar regras."
Sprint 5 — Polimento e Otimização.

Regras canônicas:
  - Streak atual: dias consecutivos até hoje OU ontem (janela de graça de 1 dia)
  - Melhor streak: maior sequência histórica de dias consecutivos
  - Dias sem atividade: diferença em dias do último registro até hoje
"""
from __future__ import annotations

from datetime import date, timedelta


def calculate_streak(dates: list[date]) -> int:
    """
    Calcula streak atual a partir de lista de datas.

    Regra: conta dias consecutivos terminando em hoje ou ontem.
    A janela de graça de 1 dia evita que o paciente perca o streak
    se registrar a atividade tarde da noite.

    Args:
        dates: Lista de datas (qualquer ordem — será ordenada internamente).

    Returns:
        Número de dias consecutivos do streak atual. 0 se não há streak.

    Examples:
        >>> from datetime import date, timedelta
        >>> hoje = date.today()
        >>> calculate_streak([hoje, hoje - timedelta(1), hoje - timedelta(2)])
        3
        >>> calculate_streak([hoje - timedelta(3), hoje - timedelta(4)])
        0  # último registro foi há 3 dias — streak quebrado
    """
    if not dates:
        return 0

    sorted_dates = sorted(set(dates))
    today = date.today()
    yesterday = today - timedelta(days=1)

    last = sorted_dates[-1]
    if last not in (today, yesterday):
        return 0

    streak = 1
    check = last
    for d in reversed(sorted_dates[:-1]):
        if (check - d).days == 1:
            streak += 1
            check = d
        else:
            break

    return streak


def calculate_best_streak(dates: list[date]) -> int:
    """
    Calcula o maior streak histórico a partir de lista de datas.

    Percorre todas as sequências consecutivas e retorna a maior.

    Args:
        dates: Lista de datas (qualquer ordem — será ordenada internamente).

    Returns:
        Tamanho do maior streak encontrado. 0 se lista vazia.

    Examples:
        >>> from datetime import date, timedelta
        >>> hoje = date.today()
        >>> datas = [hoje - timedelta(i) for i in range(5)]  # 5 dias consecutivos
        >>> calculate_best_streak(datas)
        5
    """
    if not dates:
        return 0

    sorted_dates = sorted(set(dates))

    if len(sorted_dates) == 1:
        return 1

    best = 1
    current = 1

    for i in range(1, len(sorted_dates)):
        delta = (sorted_dates[i] - sorted_dates[i - 1]).days
        if delta == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1

    return best


def days_without_activity(dates: list[date]) -> int:
    """
    Calcula quantos dias se passaram desde o último registro.

    Args:
        dates: Lista de datas de atividade.

    Returns:
        Dias desde a última atividade. -1 se não há registros.

    Examples:
        >>> from datetime import date, timedelta
        >>> days_without_activity([date.today() - timedelta(3)])
        3
        >>> days_without_activity([date.today()])
        0
    """
    if not dates:
        return -1

    last = max(dates)
    return (date.today() - last).days


def streak_at_risk(dates: list[date], min_streak: int = 3) -> bool:
    """
    Verifica se um streak valioso está em risco (atividade não feita hoje).

    Usado pelo scheduler de notificações para decidir quem alertar.

    Args:
        dates: Lista de datas de atividade.
        min_streak: Streak mínimo para considerar valioso (padrão: 3).

    Returns:
        True se há streak >= min_streak E a atividade não foi feita hoje.
    """
    today = date.today()
    if today in dates:
        return False  # já fez hoje — sem risco

    yesterday = today - timedelta(days=1)
    streak = calculate_streak(dates)
    return streak >= min_streak and (not dates or max(dates) == yesterday)
