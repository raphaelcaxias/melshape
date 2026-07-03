"""views.professional.triage_panel — alias para professional.triage_panel"""
try:
    from professional.triage_panel import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from professional.triage_panel import render
except ImportError:
    pass
