"""Backend router for SDK - routes events to configured backends."""

from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import MonitoringConfig, SDKMode, BackendType
from .backends import Backend, BackendResult, BackendStatus
from .backends.sidecar import SidecarBackend
from .backends.filesystem import FileSystemBackend
from .backends.s3 import S3Backend
from .backends.elk import ELKBackend

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# Registry of available backend classes
BACKEND_REGISTRY = {
    BackendType.SIDECAR: SidecarBackend,
    BackendType.FILESYSTEM: FileSystemBackend,
    BackendType.S3: S3Backend,
    BackendType.ELK: ELKBackend,
}


class BackendRouter:
    """
    Routes events to multiple backends based on configuration.
    
    Features:
    - Multiple backend support
    - Concurrent delivery (threaded)
    - Fallback on failure
    - Health checking
    """
    
    def __init__(self, config: MonitoringConfig):
        """
        Initialize the router.
        
        Args:
            config: MonitoringConfig instance
        """
        self.config = config
        self.backends: List[Backend] = []
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._initialize_backends()
    
    def _initialize_backends(self) -> None:
        """Initialize backends based on configuration."""
        if self.config.mode == SDKMode.SIDECAR:
            # Sidecar mode: only use sidecar backend
            backend = SidecarBackend({
                'url': self.config.sidecar.url,
                'timeout': self.config.sidecar.timeout,
                'retries': self.config.sidecar.retries
            })
            self.backends.append(backend)
            logger.info("router_initialized", mode="sidecar")
        
        elif self.config.mode == SDKMode.DIRECT:
            # Direct mode: use configured backends
            for backend_config in self.config.get_active_backends():
                backend_class = BACKEND_REGISTRY.get(backend_config.type)
                
                if backend_class is None:
                    logger.warning(
                        "unknown_backend_type",
                        type=backend_config.type
                    )
                    continue
                
                try:
                    backend = backend_class(backend_config.config)
                    self.backends.append(backend)
                    logger.info(
                        "backend_added",
                        type=backend_config.type,
                        priority=backend_config.priority
                    )
                except Exception as e:
                    logger.error(
                        "backend_initialization_failed",
                        type=backend_config.type,
                        error=str(e)
                    )
        
        # Initialize all backends
        for backend in self.backends:
            try:
                backend.initialize()
            except Exception as e:
                logger.error(
                    "backend_init_failed",
                    backend=type(backend).__name__,
                    error=str(e)
                )
    
    def send_event(self, event: Dict[str, Any]) -> Dict[str, BackendResult]:
        """
        Send event to all configured backends concurrently.
        
        Args:
            event: Event dictionary
            
        Returns:
            Dictionary mapping backend name to BackendResult
        """
        if not self.backends:
            logger.warning("no_backends_configured")
            return {}
        
        results = {}
        
        # Submit to all backends concurrently
        futures = {}
        for backend in self.backends:
            if backend.is_enabled():
                future = self._executor.submit(backend.send_event, event)
                futures[future] = type(backend).__name__
        
        # Collect results
        for future in as_completed(futures):
            backend_name = futures[future]
            try:
                result = future.result(timeout=10.0)
                results[backend_name] = result
                
                if result.success:
                    logger.debug(
                        "backend_send_success",
                        backend=backend_name
                    )
                else:
                    logger.warning(
                        "backend_send_failed",
                        backend=backend_name,
                        error=result.message
                    )
            
            except Exception as e:
                logger.error(
                    "backend_send_error",
                    backend=backend_name,
                    error=str(e)
                )
                results[backend_name] = BackendResult(
                    status=BackendStatus.FAILED,
                    message=f"Exception: {str(e)}",
                    events_failed=1,
                    error=e
                )
        
        return results
    
    def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, BackendResult]:
        """
        Send batch of events to all configured backends concurrently.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            Dictionary mapping backend name to BackendResult
        """
        if not self.backends:
            logger.warning("no_backends_configured")
            return {}
        
        results = {}
        
        # Submit to all backends concurrently
        futures = {}
        for backend in self.backends:
            if backend.is_enabled():
                future = self._executor.submit(backend.send_batch, events)
                futures[future] = type(backend).__name__
        
        # Collect results
        for future in as_completed(futures):
            backend_name = futures[future]
            try:
                result = future.result(timeout=30.0)
                results[backend_name] = result
                
                if result.success:
                    logger.debug(
                        "backend_batch_success",
                        backend=backend_name,
                        count=len(events)
                    )
                else:
                    logger.warning(
                        "backend_batch_failed",
                        backend=backend_name,
                        error=result.message
                    )
            
            except Exception as e:
                logger.error(
                    "backend_batch_error",
                    backend=backend_name,
                    error=str(e)
                )
                results[backend_name] = BackendResult(
                    status=BackendStatus.FAILED,
                    message=f"Exception: {str(e)}",
                    events_failed=len(events),
                    error=e
                )
        
        return results
    
    def health_check(self) -> Dict[str, bool]:
        """
        Check health of all backends.
        
        Returns:
            Dictionary mapping backend name to health status
        """
        health = {}
        
        for backend in self.backends:
            backend_name = type(backend).__name__
            try:
                health[backend_name] = backend.health_check()
            except Exception as e:
                logger.error(
                    "backend_health_check_failed",
                    backend=backend_name,
                    error=str(e)
                )
                health[backend_name] = False
        
        return health
    
    def close(self) -> None:
        """Close all backends and cleanup."""
        for backend in self.backends:
            try:
                backend.close()
            except Exception as e:
                logger.error(
                    "backend_close_failed",
                    backend=type(backend).__name__,
                    error=str(e)
                )
        
        self._executor.shutdown(wait=True)
        logger.info("router_closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

