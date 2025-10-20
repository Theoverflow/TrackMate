"""
Wafer Monitor SDK - Mission-critical sidecar monitoring client.

Enhanced with multi-backend support and flexible routing.
"""

from .models import AppRef, EntityRef, EventPayload, JobEvent
from .emitter import SidecarEmitter
from .context import Monitored
from .config import (
    MonitoringConfig,
    SDKMode,
    BackendType,
    SidecarConfig,
    BackendConfig,
    AppConfig,
    configure,
    get_config,
    reset_config
)
from .router import BackendRouter
from .backends import (
    Backend,
    BackendResult,
    SidecarBackend,
    FileSystemBackend,
    S3Backend,
    ELKBackend
)

# AWS helpers are optional
try:
    from . import aws_helpers
    __all__ = [
        # Core SDK
        'AppRef', 'EntityRef', 'EventPayload', 'JobEvent',
        'SidecarEmitter', 'Monitored',
        # Configuration
        'MonitoringConfig', 'SDKMode', 'BackendType',
        'SidecarConfig', 'BackendConfig', 'AppConfig',
        'configure', 'get_config', 'reset_config',
        # Routing
        'BackendRouter',
        # Backends
        'Backend', 'BackendResult',
        'SidecarBackend', 'FileSystemBackend', 'S3Backend', 'ELKBackend',
        # AWS
        'aws_helpers'
    ]
except ImportError:
    __all__ = [
        # Core SDK
        'AppRef', 'EntityRef', 'EventPayload', 'JobEvent',
        'SidecarEmitter', 'Monitored',
        # Configuration
        'MonitoringConfig', 'SDKMode', 'BackendType',
        'SidecarConfig', 'BackendConfig', 'AppConfig',
        'configure', 'get_config', 'reset_config',
        # Routing
        'BackendRouter',
        # Backends
        'Backend', 'BackendResult',
        'SidecarBackend', 'FileSystemBackend', 'S3Backend', 'ELKBackend'
    ]

__version__ = "0.3.0"

