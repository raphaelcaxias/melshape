"""views.patient.complete_evolution — alias para patient.complete_evolution"""
try:
    from patient.complete_evolution import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.complete_evolution import render
except ImportError:
    pass
