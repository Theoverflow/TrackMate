"""Managed API Backend - forwards events to Local API."""

import time
import httpx
from typing import Dict, Any, List

from ..backend_router import SidecarBackend, BackendResult

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ManagedAPIBackend(SidecarBackend):
    """
    Managed API backend for sidecar.
    
    Forwards events to the Local API (managed TimescaleDB endpoint).
    
    Configuration:
        url: Local API URL (e.g., http://local-api:18000)
        endpoint: API endpoint path (default: /v1/ingest/managed)
        timeout: Request timeout in seconds (default: 10.0)
        verify_ssl: Verify SSL certificates (default: True)
        batch_size: Maximum events per batch (default: 100)
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.url = config.config.get('url', 'http://localhost:18000')
        self.endpoint = config.config.get('endpoint', '/v1/ingest/managed')
        self.timeout = config.config.get('timeout', 10.0)
        self.verify_ssl = config.config.get('verify_ssl', True)
        self.batch_size = config.config.get('batch_size', 100)
        self._client = None
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.url,
            timeout=self.timeout,
            verify=self.verify_ssl,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50
            )
        )
        logger.info("managed_api_backend_initialized", url=self.url)
    
    async def send_event(self, event: Dict[str, Any]) -> BackendResult:
        """
        Send a single event to managed API.
        
        Args:
            event: Event dictionary
            
        Returns:
            BackendResult with operation status
        """
        start_time = time.time()
        
        try:
            response = await self._client.post(
                self.endpoint,
                json={'events': [event]}
            )
            response.raise_for_status()
            
            latency_ms = (time.time() - start_time) * 1000
            
            logger.debug(
                "event_sent_to_managed_api",
                event_id=event.get('idempotency_key'),
                latency_ms=latency_ms
            )
            
            return BackendResult(
                backend_name="managed_api",
                success=True,
                events_sent=1,
                latency_ms=latency_ms
            )
        
        except httpx.HTTPError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "managed_api_send_failed",
                error=str(e),
                event_id=event.get('idempotency_key')
            )
            return BackendResult(
                backend_name="managed_api",
                success=False,
                events_failed=1,
                error=str(e),
                latency_ms=latency_ms
            )
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "managed_api_send_error",
                error=str(e),
                error_type=type(e).__name__
            )
            return BackendResult(
                backend_name="managed_api",
                success=False,
                events_failed=1,
                error=str(e),
                latency_ms=latency_ms
            )
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> BackendResult:
        """
        Send a batch of events to managed API.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            BackendResult with operation status
        """
        start_time = time.time()
        
        # Split into chunks if batch is too large
        chunks = [events[i:i + self.batch_size] 
                  for i in range(0, len(events), self.batch_size)]
        
        total_sent = 0
        total_failed = 0
        errors = []
        
        for chunk in chunks:
            try:
                response = await self._client.post(
                    self.endpoint,
                    json={'events': chunk}
                )
                response.raise_for_status()
                total_sent += len(chunk)
            
            except httpx.HTTPError as e:
                logger.error(
                    "managed_api_batch_chunk_failed",
                    error=str(e),
                    chunk_size=len(chunk)
                )
                total_failed += len(chunk)
                errors.append(str(e))
            
            except Exception as e:
                logger.error(
                    "managed_api_batch_chunk_error",
                    error=str(e),
                    error_type=type(e).__name__
                )
                total_failed += len(chunk)
                errors.append(str(e))
        
        latency_ms = (time.time() - start_time) * 1000
        
        logger.debug(
            "batch_sent_to_managed_api",
            total=len(events),
            sent=total_sent,
            failed=total_failed,
            latency_ms=latency_ms
        )
        
        return BackendResult(
            backend_name="managed_api",
            success=(total_failed == 0),
            events_sent=total_sent,
            events_failed=total_failed,
            error="; ".join(errors) if errors else None,
            latency_ms=latency_ms
        )
    
    async def health_check(self) -> bool:
        """Check if managed API is reachable."""
        try:
            response = await self._client.get('/health', timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            logger.info("managed_api_backend_closed")

