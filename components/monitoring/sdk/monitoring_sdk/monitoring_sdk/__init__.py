"""Wafer Monitor SDK - Mission-critical sidecar monitoring client."""
from .models import AppRef, EntityRef, EventPayload, JobEvent
from .emitter import SidecarEmitter
from .context import Monitored

# AWS helpers are optional
try:
    from . import aws_helpers
    __all__ = ['AppRef','EntityRef','EventPayload','JobEvent','SidecarEmitter','Monitored','aws_helpers']
except ImportError:
    __all__ = ['AppRef','EntityRef','EventPayload','JobEvent','SidecarEmitter','Monitored']

__version__ = "0.2.0"
