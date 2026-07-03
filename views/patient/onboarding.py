"""views.patient.onboarding — alias para patient.onboarding"""
try:
    from patient.onboarding import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.onboarding import render
except ImportError:
    pass
