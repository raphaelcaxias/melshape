"""views.patient.register_hub_quick — alias"""
from patient.register_hub_quick import _form_agua, _form_checkin  # noqa: F401
try:
    from patient.register_hub_quick import render
except ImportError:
    pass
