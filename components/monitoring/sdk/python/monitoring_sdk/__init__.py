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

# Runtime configuration (hot-reloading)
try:
    from .runtime_config import RuntimeConfigManager, init_with_runtime_config
    _has_runtime_config = True
except ImportError:
    _has_runtime_config = False

# Build exports list
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
]

# Add AWS helpers if available
try:
    from . import aws_helpers
    __all__.append('aws_helpers')
except ImportError:
    pass

# Add runtime config if available
if _has_runtime_config:
    __all__.extend(['RuntimeConfigManager', 'init_with_runtime_config'])

__version__ = "0.3.0"

