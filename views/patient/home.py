"""views.patient.home — alias para patient.home"""
try:
    from patient.home import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.home import render
except ImportError:
    pass
