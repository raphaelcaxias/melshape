"""
Melshape — Home: funções auxiliares de busca de dados.

Extraídas de home.py para permitir que os métodos cacheados com
@st.cache_data(ttl=60) passem _self como primeiro argumento (workaround
Streamlit para cache em métodos de instância).

Importado por home.py:
    from views.patient.home_helpers import _get_last_weight, _get_dashboard_paciente
"""
from __future__ import annotations

from typing import Any


def _get_last_weight(db: Any) -> float | None:
    """Obtém o último peso registrado pelo paciente.

    Args:
        db: Instância do Database (real ou mock).

    Returns:
        Último peso em kg, ou None se não houver registros.
    """
    try:
        weights = db.get_weights(30)
        if weights is not None and not weights.empty:
            return float(weights.iloc[-1]["weight"])
        return None
    except Exception:
        return None


def _get_dashboard_paciente(db: Any) -> dict[str, Any]:
    """Obtém dados resumidos do dashboard do paciente.

    Busca total de badges e desafios concluídos localmente.
    Usado pelo bloco de XP/gamificação na home.

    Args:
        db: Instância do Database (real ou mock).

    Returns:
        Dict com total_badges e desafios_concluidos.
    """
    try:
        total_badges = len(db.get_achievements() or [])
    except Exception:
        total_badges = 0

    # desafios locais ficam na session_state (sem acesso ao st aqui)
    # home.py passa esse valor via _get_dashboard_paciente(_self.db)
    # e o resultado é complementado pelo caller com dados da session
    return {
        "total_badges": total_badges,
        "desafios_concluidos": 0,  # complementado em home.py via session_state
    }
