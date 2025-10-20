"""Sidecar backend - forwards events to sidecar agent via HTTP."""

import httpx
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import Backend, BackendResult, BackendStatus

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class SidecarBackend(Backend):
    """
    Sidecar backend implementation.
    
    Sends events to a sidecar agent via HTTP POST.
    The sidecar handles routing to final destinations.
    
    Configuration:
        url: Sidecar URL (default: http://localhost:17000)
        timeout: Request timeout in seconds (default: 5.0)
        retries: Number of retry attempts (default: 3)
        verify_ssl: Verify SSL certificates (default: True)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get('url', 'http://localhost:17000')
        self.timeout = config.get('timeout', 5.0)
        self.max_retries = config.get('retries', 3)
        self.verify_ssl = config.get('verify_ssl', True)
        self._client = None
    
    def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.Client(
            base_url=self.url,
            timeout=self.timeout,
            verify=self.verify_ssl,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20
            )
        )
        self._initialized = True
        logger.info("sidecar_backend_initialized", url=self.url)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=0.1, max=2.0),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True
    )
    def send_event(self, event: Dict[str, Any]) -> BackendResult:
        """
        Send a single event to sidecar.
        
        Args:
            event: Event dictionary
            
        Returns:
            BackendResult with operation status
        """
        if not self._initialized:
            self.initialize()
        
        try:
            response = self._client.post('/v1/ingest/events', json=event)
            response.raise_for_status()
            
            logger.debug("event_sent_to_sidecar", event_id=event.get('idempotency_key'))
            
            return BackendResult(
                status=BackendStatus.SUCCESS,
                message="Event sent successfully",
                events_sent=1
            )
        
        except httpx.HTTPError as e:
            logger.error(
                "sidecar_send_failed",
                error=str(e),
                event_id=event.get('idempotency_key')
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"HTTP error: {str(e)}",
                events_failed=1,
                error=e
            )
        
        except Exception as e:
            logger.error(
                "sidecar_send_error",
                error=str(e),
                error_type=type(e).__name__
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"Error: {str(e)}",
                events_failed=1,
                error=e
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=0.1, max=2.0),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True
    )
    def send_batch(self, events: List[Dict[str, Any]]) -> BackendResult:
        """
        Send a batch of events to sidecar.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            BackendResult with operation status
        """
        if not self._initialized:
            self.initialize()
        
        try:
            response = self._client.post('/v1/ingest/batch', json={'events': events})
            response.raise_for_status()
            
            logger.debug("batch_sent_to_sidecar", count=len(events))
            
            return BackendResult(
                status=BackendStatus.SUCCESS,
                message=f"Batch of {len(events)} events sent successfully",
                events_sent=len(events)
            )
        
        except httpx.HTTPError as e:
            logger.error(
                "sidecar_batch_send_failed",
                error=str(e),
                count=len(events)
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"HTTP error: {str(e)}",
                events_failed=len(events),
                error=e
            )
        
        except Exception as e:
            logger.error(
                "sidecar_batch_send_error",
                error=str(e),
                error_type=type(e).__name__
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"Error: {str(e)}",
                events_failed=len(events),
                error=e
            )
    
    def health_check(self) -> bool:
        """Check if sidecar is reachable."""
        if not self._initialized:
            return False
        
        try:
            response = self._client.get('/health', timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False
    
    def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._initialized = False
            logger.info("sidecar_backend_closed")

