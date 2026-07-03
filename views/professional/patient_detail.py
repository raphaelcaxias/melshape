"""views.professional.patient_detail — alias para professional.patient_detail"""
try:
    from professional.patient_detail import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from professional.patient_detail import render
except ImportError:
    pass
