"""views.patient.share_card — alias para patient.share_card"""
try:
    from patient.share_card import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.share_card import render
except ImportError:
    pass
