"""
Backend router for Sidecar Agent.

Routes incoming events to multiple backend destinations concurrently.
"""

import asyncio
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import json

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class BackendType(str, Enum):
    """Backend types supported by sidecar."""
    MANAGED_API = "managed_api"
    FILESYSTEM = "filesystem"
    S3 = "s3"
    ELK = "elk"
    ZABBIX = "zabbix"
    CLOUDWATCH = "cloudwatch"
    WEBHOOK = "webhook"
    KAFKA = "kafka"
    SQS = "sqs"


class BackendStatus(str, Enum):
    """Backend health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class BackendConfig:
    """Configuration for a sidecar backend."""
    type: BackendType
    enabled: bool = True
    priority: int = 1
    config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}


@dataclass
class BackendResult:
    """Result of a backend operation."""
    backend_name: str
    success: bool
    events_sent: int = 0
    events_failed: int = 0
    error: Optional[str] = None
    latency_ms: float = 0.0


class SidecarBackend:
    """
    Base class for sidecar backends.
    
    All sidecar backend implementations should inherit from this.
    """
    
    def __init__(self, config: BackendConfig):
        self.config = config
        self.type = config.type
        self.enabled = config.enabled
        self.priority = config.priority
        self._status = BackendStatus.HEALTHY
        self._failure_count = 0
        self._max_failures = 5
    
    async def initialize(self) -> None:
        """Initialize the backend. Override in subclasses."""
        pass
    
    async def send_event(self, event: Dict[str, Any]) -> BackendResult:
        """Send a single event. Override in subclasses."""
        raise NotImplementedError
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> BackendResult:
        """Send a batch of events. Override in subclasses."""
        raise NotImplementedError
    
    async def health_check(self) -> bool:
        """Check backend health. Override in subclasses."""
        return True
    
    async def close(self) -> None:
        """Close backend. Override in subclasses."""
        pass
    
    def record_success(self) -> None:
        """Record successful operation."""
        if self._failure_count > 0:
            self._failure_count -= 1
        if self._failure_count == 0:
            self._status = BackendStatus.HEALTHY
    
    def record_failure(self) -> None:
        """Record failed operation."""
        self._failure_count += 1
        if self._failure_count >= self._max_failures:
            self._status = BackendStatus.FAILED
            logger.error(
                "backend_circuit_open",
                backend=self.type,
                failures=self._failure_count
            )
        elif self._failure_count > 2:
            self._status = BackendStatus.DEGRADED
    
    def is_healthy(self) -> bool:
        """Check if backend is in healthy state."""
        return self._status == BackendStatus.HEALTHY
    
    def is_available(self) -> bool:
        """Check if backend is available (not in failed state)."""
        return self._status != BackendStatus.FAILED
    
    def get_status(self) -> BackendStatus:
        """Get current backend status."""
        return self._status


class BackendRouter:
    """
    Routes events to multiple backends concurrently.
    
    Features:
    - Priority-based routing
    - Circuit breaker pattern
    - Concurrent delivery
    - Metrics collection
    """
    
    def __init__(self, backends: List[SidecarBackend]):
        """
        Initialize router with backends.
        
        Args:
            backends: List of SidecarBackend instances
        """
        self.backends = sorted(backends, key=lambda b: b.priority)
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all backends."""
        init_tasks = []
        for backend in self.backends:
            if backend.enabled:
                init_tasks.append(backend.initialize())
        
        await asyncio.gather(*init_tasks, return_exceptions=True)
        self._initialized = True
        logger.info("backend_router_initialized", count=len(self.backends))
    
    async def route_event(self, event: Dict[str, Any]) -> Dict[str, BackendResult]:
        """
        Route event to all enabled backends concurrently.
        
        Args:
            event: Event dictionary
            
        Returns:
            Dictionary mapping backend type to BackendResult
        """
        if not self._initialized:
            await self.initialize()
        
        # Create tasks for all available backends
        tasks = []
        backend_names = []
        
        for backend in self.backends:
            if backend.enabled and backend.is_available():
                tasks.append(backend.send_event(event))
                backend_names.append(backend.type.value)
        
        if not tasks:
            logger.warning("no_backends_available")
            return {}
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        backend_results = {}
        for backend_name, result in zip(backend_names, results):
            if isinstance(result, Exception):
                logger.error(
                    "backend_send_failed",
                    backend=backend_name,
                    error=str(result)
                )
                backend_results[backend_name] = BackendResult(
                    backend_name=backend_name,
                    success=False,
                    events_failed=1,
                    error=str(result)
                )
            else:
                backend_results[backend_name] = result
                
                # Update circuit breaker state
                backend = next(b for b in self.backends if b.type.value == backend_name)
                if result.success:
                    backend.record_success()
                else:
                    backend.record_failure()
        
        return backend_results
    
    async def route_batch(self, events: List[Dict[str, Any]]) -> Dict[str, BackendResult]:
        """
        Route batch of events to all enabled backends concurrently.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            Dictionary mapping backend type to BackendResult
        """
        if not self._initialized:
            await self.initialize()
        
        # Create tasks for all available backends
        tasks = []
        backend_names = []
        
        for backend in self.backends:
            if backend.enabled and backend.is_available():
                tasks.append(backend.send_batch(events))
                backend_names.append(backend.type.value)
        
        if not tasks:
            logger.warning("no_backends_available_for_batch")
            return {}
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        backend_results = {}
        for backend_name, result in zip(backend_names, results):
            if isinstance(result, Exception):
                logger.error(
                    "backend_batch_failed",
                    backend=backend_name,
                    error=str(result),
                    count=len(events)
                )
                backend_results[backend_name] = BackendResult(
                    backend_name=backend_name,
                    success=False,
                    events_failed=len(events),
                    error=str(result)
                )
            else:
                backend_results[backend_name] = result
                
                # Update circuit breaker state
                backend = next(b for b in self.backends if b.type.value == backend_name)
                if result.success:
                    backend.record_success()
                else:
                    backend.record_failure()
        
        return backend_results
    
    async def health_check(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all backends.
        
        Returns:
            Dictionary mapping backend type to health info
        """
        health_tasks = []
        backend_names = []
        
        for backend in self.backends:
            if backend.enabled:
                health_tasks.append(backend.health_check())
                backend_names.append(backend.type.value)
        
        results = await asyncio.gather(*health_tasks, return_exceptions=True)
        
        health_status = {}
        for backend_name, result in zip(backend_names, results):
            backend = next(b for b in self.backends if b.type.value == backend_name)
            
            if isinstance(result, Exception):
                health_status[backend_name] = {
                    "healthy": False,
                    "status": BackendStatus.FAILED.value,
                    "error": str(result)
                }
            else:
                health_status[backend_name] = {
                    "healthy": result,
                    "status": backend.get_status().value,
                    "failure_count": backend._failure_count
                }
        
        return health_status
    
    async def close(self) -> None:
        """Close all backends."""
        close_tasks = []
        for backend in self.backends:
            close_tasks.append(backend.close())
        
        await asyncio.gather(*close_tasks, return_exceptions=True)
        logger.info("backend_router_closed")
    
    def get_status(self) -> Dict[str, Any]:
        """Get router status."""
        return {
            "backends_total": len(self.backends),
            "backends_enabled": sum(1 for b in self.backends if b.enabled),
            "backends_healthy": sum(1 for b in self.backends if b.is_healthy()),
            "backends_degraded": sum(1 for b in self.backends if b.get_status() == BackendStatus.DEGRADED),
            "backends_failed": sum(1 for b in self.backends if b.get_status() == BackendStatus.FAILED)
        }


class BackendRegistry:
    """Registry of available backend implementations."""
    
    _backends = {}
    
    @classmethod
    def register(cls, backend_type: BackendType, backend_class: type):
        """Register a backend implementation."""
        cls._backends[backend_type] = backend_class
        logger.debug("backend_registered", type=backend_type)
    
    @classmethod
    def create(cls, config: BackendConfig) -> SidecarBackend:
        """Create a backend instance from configuration."""
        backend_class = cls._backends.get(config.type)
        
        if backend_class is None:
            raise ValueError(f"Unknown backend type: {config.type}")
        
        return backend_class(config)
    
    @classmethod
    def get_available_types(cls) -> List[BackendType]:
        """Get list of registered backend types."""
        return list(cls._backends.keys())


def load_config(config_path: Path) -> List[BackendConfig]:
    """
    Load backend configurations from file.
    
    Args:
        config_path: Path to configuration file (JSON or YAML)
        
    Returns:
        List of BackendConfig instances
    """
    with open(config_path, 'r') as f:
        if config_path.suffix == '.json':
            data = json.load(f)
        elif config_path.suffix in ['.yaml', '.yml']:
            import yaml
            data = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported config format: {config_path.suffix}")
    
    backends = []
    for backend_data in data.get('backends', []):
        backend = BackendConfig(
            type=BackendType(backend_data['type']),
            enabled=backend_data.get('enabled', True),
            priority=backend_data.get('priority', 1),
            config=backend_data.get('config', {})
        )
        backends.append(backend)
    
    return backends

