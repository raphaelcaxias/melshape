"""views.professional.executive_dashboard — alias para professional.executive_dashboard"""
try:
    from professional.executive_dashboard import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from professional.executive_dashboard import render
except ImportError:
    pass
