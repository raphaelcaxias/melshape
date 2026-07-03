"""views.professional.dashboard_pro — alias para professional.dashboard_pro"""
try:
    from professional.dashboard_pro import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from professional.dashboard_pro import render
except ImportError:
    pass
