"""views.auth.login — alias para auth.login"""
from auth.login import *  # noqa: F401, F403
try:
    from auth.login import render
except ImportError:
    pass
