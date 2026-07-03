"""views.patient.habits — alias para patient.habits"""
try:
    from patient.habits import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.habits import render
except ImportError:
    pass
