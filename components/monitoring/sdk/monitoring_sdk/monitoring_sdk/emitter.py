import os
import httpx
from typing import Iterable, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .models import JobEvent

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore

DEFAULT_TIMEOUT = 5.0
MAX_RETRIES = 3
RETRY_MIN_WAIT = 0.1
RETRY_MAX_WAIT = 2.0


class SidecarEmitter:
    """
    HTTP client to send JobEvents to the sidecar agent (Env A).
    Sidecar forwards to Local API (Env B).
    
    Features:
    - Automatic retries with exponential backoff
    - Structured logging of all operations
    - Connection pooling for better performance
    - Graceful error handling with fallback options
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        enable_retries: bool = True
    ):
        """
        Initialize the emitter.
        
        Args:
            base_url: Sidecar agent URL (defaults to SIDECAR_URL env var)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            enable_retries: Whether to enable automatic retries
        """
        self.base_url = base_url or os.getenv('SIDECAR_URL', 'http://localhost:8000')
        self.timeout = timeout
        self.max_retries = max_retries if enable_retries else 1
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        logger.info("emitter_initialized", base_url=self.base_url, timeout=timeout)
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True
    )
    def send(self, ev: JobEvent) -> None:
        """
        Send a single event to the sidecar agent.
        
        Args:
            ev: JobEvent to send
            
        Raises:
            httpx.HTTPError: If the request fails after retries
        """
        try:
            logger.debug(
                "sending_event",
                event_kind=ev.event.kind,
                entity_type=ev.entity.type,
                entity_id=str(ev.entity.id)
            )
            r = self._client.post('/v1/ingest/events', json=ev.to_json())
            r.raise_for_status()
            logger.info(
                "event_sent",
                event_kind=ev.event.kind,
                entity_type=ev.entity.type,
                status_code=r.status_code
            )
        except httpx.HTTPError as e:
            logger.error(
                "event_send_failed",
                event_kind=ev.event.kind,
                entity_type=ev.entity.type,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True
    )
    def send_batch(self, events: Iterable[JobEvent]) -> None:
        """
        Send a batch of events to the sidecar agent.
        
        Args:
            events: Iterable of JobEvents to send
            
        Raises:
            httpx.HTTPError: If the request fails after retries
        """
        event_list = list(events)
        try:
            logger.debug("sending_batch", count=len(event_list))
            payload = [e.to_json() for e in event_list]
            r = self._client.post('/v1/ingest/events:batch', json=payload)
            r.raise_for_status()
            logger.info(
                "batch_sent",
                count=len(event_list),
                status_code=r.status_code
            )
        except httpx.HTTPError as e:
            logger.error(
                "batch_send_failed",
                count=len(event_list),
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self._client.close()
        logger.info("emitter_closed")
    
    def __enter__(self) -> 'SidecarEmitter':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        """Context manager exit."""
        self.close()
        return False
