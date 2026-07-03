"""views.auth.forgot_password — alias para auth.forgot_password"""
from auth.forgot_password import *  # noqa: F401, F403
try:
    from auth.forgot_password import render
except ImportError:
    pass
