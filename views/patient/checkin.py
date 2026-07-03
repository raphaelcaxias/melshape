"""views.patient.checkin — alias para patient.checkin"""
try:
    from patient.checkin import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.checkin import render
except ImportError:
    pass
