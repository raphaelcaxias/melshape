"""views.patient.profile — alias para patient.profile"""
try:
    from patient.profile import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.profile import render
except ImportError:
    pass
