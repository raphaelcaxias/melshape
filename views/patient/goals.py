"""views.patient.goals — alias para patient.goals"""
try:
    from patient.goals import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.goals import render
except ImportError:
    pass
