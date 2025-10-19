"""Local API integration - original integration method."""
import httpx
from typing import Dict, Any, List
from .base import BaseIntegration, IntegrationConfig

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class LocalAPIIntegration(BaseIntegration):
    """
    Integration with Local API (TimescaleDB backend).
    
    This is the primary integration for the wafer monitoring system.
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize Local API integration."""
        super().__init__(config)
        self.base_url = self.get_config('base_url', 'http://localhost:18000')
        self.timeout = self.get_config('timeout', 5.0)
        self.client: httpx.AsyncClient = None
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        self._initialized = True
        logger.info(
            "local_api_integration_initialized",
            name=self.name,
            base_url=self.base_url
        )
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """Send single event to Local API."""
        try:
            r = await self.client.post('/v1/ingest/events', json=event)
            r.raise_for_status()
            logger.debug("event_sent_to_local_api", idempotency_key=event.get('idempotency_key'))
            return True
        except Exception as e:
            logger.error(
                "local_api_send_failed",
                error=str(e),
                idempotency_key=event.get('idempotency_key')
            )
            return False
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Send batch of events to Local API."""
        try:
            r = await self.client.post('/v1/ingest/events:batch', json=events)
            r.raise_for_status()
            result = r.json()
            
            success = result.get('forwarded', len(events))
            failed = len(events) - success
            
            logger.info(
                "batch_sent_to_local_api",
                total=len(events),
                success=success,
                failed=failed
            )
            return {'success': success, 'failed': failed}
        except Exception as e:
            logger.error("local_api_batch_failed", error=str(e), count=len(events))
            return {'success': 0, 'failed': len(events)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Local API health."""
        try:
            r = await self.client.get('/v1/healthz', timeout=2.0)
            r.raise_for_status()
            data = r.json()
            return {
                'status': 'healthy',
                'integration': self.name,
                'backend': 'local_api',
                'details': data
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'integration': self.name,
                'backend': 'local_api',
                'error': str(e)
            }
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
        logger.info("local_api_integration_closed", name=self.name)

