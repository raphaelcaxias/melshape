"""views.patient.journey_timeline — alias"""
try:
    from patient.journey_timeline import (
        render_linha_do_tempo, render_marcos, _tab_todas_etapas
    )
except ImportError:
    pass
