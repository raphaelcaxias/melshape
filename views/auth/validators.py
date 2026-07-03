"""views.auth.validators — alias para auth.validators"""
from auth.validators import *  # noqa: F401, F403
try:
    from auth.validators import render
except ImportError:
    pass
