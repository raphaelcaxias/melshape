"""views.patient.bariatric — alias para patient.bariatric"""
try:
    from patient.bariatric import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.bariatric import render
except ImportError:
    pass
