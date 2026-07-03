"""views.patient.journey_story — alias para patient.journey_story"""
try:
    from patient.journey_story import *  # noqa: F401, F403
except ImportError:
    pass
try:
    from patient.journey_story import render
except ImportError:
    pass
