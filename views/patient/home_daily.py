"""views.patient.home_daily — alias para patient.home_daily"""
try:
    from patient.home_daily import (
        _bloco_habitos_hoje, _bloco_comportamento, _bloco_consequencias, _bloco_score
    )
except ImportError:
    pass
