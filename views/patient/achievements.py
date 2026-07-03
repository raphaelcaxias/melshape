"""views.patient.achievements — alias para patient.achievements"""
try:
    from patient.achievements import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.achievements import render
except ImportError:
    pass
