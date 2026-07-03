"""views.auth.register — alias para auth.register"""
from auth.register import *  # noqa: F401, F403
try:
    from auth.register import render
except ImportError:
    pass
