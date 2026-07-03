"""views.auth.landing — alias para auth.landing"""
from auth.landing import *  # noqa: F401, F403
try:
    from auth.landing import render
except ImportError:
    pass
