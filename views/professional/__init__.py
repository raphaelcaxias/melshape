"""
views.professional — Alias para o pacote ``professional`` (telas do profissional).

Este módulo é um proxy: qualquer import de ``views.professional.X``
resolve para ``professional.X``.

Módulos disponíveis
-------------------
dashboard_pro           Dashboard com lista de pacientes         (render)
patient_detail          Detalhamento do paciente                 (render)
executive_dashboard     Painel executivo da clínica              (render)
triage_panel            Triagem e alertas clínicos               (render_triagem)
consultation_summary_view Resumo de consulta por IA             (render)

Módulos auxiliares
------------------
dashboard_pro_tabs      Tabs do dashboard
patient_detail_charts   Gráficos do paciente
patient_detail_tabs     Tabs do paciente
patient_actions         Ações rápidas
patient_prescription    Prescrições e condutas
"""

import sys
import importlib

_real = importlib.import_module("professional")
sys.modules.setdefault("views.professional", _real)

from professional import dashboard_pro, patient_detail  # noqa: E402

__all__ = [
    "dashboard_pro",
    "patient_detail",
]
