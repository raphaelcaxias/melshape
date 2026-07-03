"""views.patient.register_hub — alias para patient.register_hub"""
try:
    from patient.register_hub import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.register_hub import render
except ImportError:
    pass
