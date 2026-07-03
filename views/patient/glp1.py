"""views.patient.glp1 — alias para patient.glp1"""
try:
    from patient.glp1 import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.glp1 import render
except ImportError:
    pass
