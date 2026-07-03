"""views.patient.journey — alias para patient.journey"""
try:
    from patient.journey import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.journey import render
except ImportError:
    pass
