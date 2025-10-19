import time
import psutil
from contextlib import ContextDecorator
from uuid import uuid4, UUID
from typing import Optional, Dict, Any
from .models import AppRef, EntityRef, JobEvent
from .emitter import SidecarEmitter

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class Monitored(ContextDecorator):
    """
    Context manager to instrument a job/subjob with automatic metrics collection.
    
    Collects:
    - CPU usage (user and system time)
    - Memory usage (RSS peak)
    - Duration
    - Success/failure status
    
    Example:
        >>> app = AppRef(app_id=uuid4(), name='my-app', version='1.0')
        >>> with Monitored(site_id='fab1', app=app, entity_type='job', business_key='batch-123'):
        ...     # Your code here
        ...     pass
    """
    
    def __init__(
        self,
        site_id: str,
        app: AppRef,
        entity_type: str,
        business_key: Optional[str] = None,
        sub_key: Optional[str] = None,
        parent_id: Optional[UUID] = None,
        emitter: Optional[SidecarEmitter] = None,
        metadata: Optional[Dict[str, Any]] = None,
        enable_logging: bool = True
    ):
        """
        Initialize the monitored context.
        
        Args:
            site_id: Site identifier (e.g., 'fab1', 'fab2')
            app: Application reference
            entity_type: Type of entity ('job' or 'subjob')
            business_key: Optional business key for correlation
            sub_key: Optional sub-key for subjobs
            parent_id: Optional parent job ID for subjobs
            emitter: Optional custom emitter (defaults to new SidecarEmitter)
            metadata: Optional metadata dict to include in events
            enable_logging: Whether to log operations
        """
        self.site_id = site_id
        self.app = app
        self.entity_id = uuid4()
        self.entity = EntityRef(
            type=entity_type,
            id=self.entity_id,
            parent_id=parent_id,
            business_key=business_key,
            sub_key=sub_key
        )
        self.metadata = metadata or {}
        self.proc = psutil.Process()
        self.emitter = emitter or SidecarEmitter()
        self._t0: Optional[float] = None
        self._cpu_t0: Optional[tuple[float, float]] = None
        self.mem_max_mb = 0.0
        self.enable_logging = enable_logging
    
    def __enter__(self) -> 'Monitored':
        """Enter the monitored context and send 'started' event."""
        self._t0 = time.perf_counter()
        cpu = self.proc.cpu_times()
        self._cpu_t0 = (cpu.user, cpu.system)
        rss = self.proc.memory_info().rss / (1024 * 1024)
        self.mem_max_mb = max(self.mem_max_mb, rss)
        
        try:
            self.emitter.send(
                JobEvent.now(
                    'started',
                    self.site_id,
                    self.app,
                    self.entity,
                    status='running',
                    metrics={
                        'cpu_user_s': 0.0,
                        'cpu_system_s': 0.0,
                        'mem_max_mb': self.mem_max_mb
                    },
                    metadata=self.metadata
                )
            )
            if self.enable_logging:
                logger.info(
                    "job_started",
                    entity_type=self.entity.type,
                    entity_id=str(self.entity_id),
                    app_name=self.app.name,
                    business_key=self.entity.business_key
                )
        except Exception as e:
            if self.enable_logging:
                logger.warning(
                    "failed_to_send_start_event",
                    error=str(e),
                    entity_id=str(self.entity_id)
                )
        
        return self
    
    def tick(self, extra_meta: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a progress update event.
        
        Args:
            extra_meta: Optional additional metadata for this tick
        """
        rss = self.proc.memory_info().rss / (1024 * 1024)
        self.mem_max_mb = max(self.mem_max_mb, rss)
        
        try:
            self.emitter.send(
                JobEvent.now(
                    'progress',
                    self.site_id,
                    self.app,
                    self.entity,
                    status='running',
                    metrics={'mem_max_mb': self.mem_max_mb},
                    metadata=extra_meta or {}
                )
            )
            if self.enable_logging:
                logger.debug(
                    "job_progress",
                    entity_id=str(self.entity_id),
                    mem_mb=round(self.mem_max_mb, 2)
                )
        except Exception as e:
            if self.enable_logging:
                logger.warning(
                    "failed_to_send_progress_event",
                    error=str(e),
                    entity_id=str(self.entity_id)
                )
    
    def __exit__(self, exc_type, exc, tb):  # type: ignore
        """Exit the monitored context and send 'finished' event."""
        cpu = self.proc.cpu_times()
        cpu_user = cpu.user - self._cpu_t0[0] if self._cpu_t0 else 0.0
        cpu_sys = cpu.system - self._cpu_t0[1] if self._cpu_t0 else 0.0
        duration = time.perf_counter() - self._t0 if self._t0 else 0.0
        rss = self.proc.memory_info().rss / (1024 * 1024)
        self.mem_max_mb = max(self.mem_max_mb, rss)
        status = 'failed' if exc else 'succeeded'
        
        metadata_final = dict(self.metadata)
        if exc:
            metadata_final['error'] = str(exc)
            metadata_final['error_type'] = type(exc).__name__
        
        try:
            self.emitter.send(
                JobEvent.now(
                    'finished',
                    self.site_id,
                    self.app,
                    self.entity,
                    status=status,
                    metrics={
                        'cpu_user_s': cpu_user,
                        'cpu_system_s': cpu_sys,
                        'mem_max_mb': self.mem_max_mb,
                        'duration_s': duration
                    },
                    metadata=metadata_final
                )
            )
            if self.enable_logging:
                logger.info(
                    "job_finished",
                    entity_type=self.entity.type,
                    entity_id=str(self.entity_id),
                    status=status,
                    duration_s=round(duration, 3),
                    cpu_user_s=round(cpu_user, 3),
                    mem_max_mb=round(self.mem_max_mb, 2)
                )
        except Exception as e:
            if self.enable_logging:
                logger.error(
                    "failed_to_send_finish_event",
                    error=str(e),
                    entity_id=str(self.entity_id)
                )
        
        return False
