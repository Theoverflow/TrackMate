"""Generic webhook integration for external systems."""
import httpx
from typing import Dict, Any, List
from .base import BaseIntegration, IntegrationConfig

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class WebhookIntegration(BaseIntegration):
    """
    Generic webhook integration for external systems.
    
    Sends events to any HTTP endpoint with configurable format.
    
    Configuration:
        - webhook_url: Target webhook URL
        - method: HTTP method (POST, PUT, PATCH) - default: POST
        - headers: Custom headers dictionary
        - timeout: Request timeout in seconds (default: 5.0)
        - verify_ssl: Verify SSL certificates (default: True)
        - retry_on_failure: Retry failed requests (default: False)
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize webhook integration."""
        super().__init__(config)
        self.webhook_url = self.get_config('webhook_url')
        self.method = self.get_config('method', 'POST').upper()
        self.custom_headers = self.get_config('headers', {})
        self.timeout = self.get_config('timeout', 5.0)
        self.verify_ssl = self.get_config('verify_ssl', True)
        self.retry_on_failure = self.get_config('retry_on_failure', False)
        self.client: httpx.AsyncClient = None
        
        if not self.webhook_url:
            raise ValueError("webhook_url is required for WebhookIntegration")
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        headers = {'Content-Type': 'application/json'}
        headers.update(self.custom_headers)
        
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=headers,
            verify=self.verify_ssl
        )
        
        self._initialized = True
        logger.info(
            "webhook_integration_initialized",
            name=self.name,
            url=self.webhook_url,
            method=self.method
        )
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """Send event to webhook."""
        try:
            if self.method == 'POST':
                r = await self.client.post(self.webhook_url, json=event)
            elif self.method == 'PUT':
                r = await self.client.put(self.webhook_url, json=event)
            elif self.method == 'PATCH':
                r = await self.client.patch(self.webhook_url, json=event)
            else:
                logger.error("unsupported_http_method", method=self.method)
                return False
            
            r.raise_for_status()
            logger.debug(
                "event_sent_to_webhook",
                url=self.webhook_url,
                status=r.status_code
            )
            return True
        except Exception as e:
            logger.error(
                "webhook_send_failed",
                url=self.webhook_url,
                error=str(e)
            )
            return False
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Send batch of events to webhook."""
        try:
            payload = {'events': events, 'count': len(events)}
            
            if self.method == 'POST':
                r = await self.client.post(self.webhook_url, json=payload)
            elif self.method == 'PUT':
                r = await self.client.put(self.webhook_url, json=payload)
            elif self.method == 'PATCH':
                r = await self.client.patch(self.webhook_url, json=payload)
            else:
                logger.error("unsupported_http_method", method=self.method)
                return {'success': 0, 'failed': len(events)}
            
            r.raise_for_status()
            
            logger.info(
                "batch_sent_to_webhook",
                url=self.webhook_url,
                count=len(events),
                status=r.status_code
            )
            return {'success': len(events), 'failed': 0}
        except Exception as e:
            logger.error(
                "webhook_batch_failed",
                url=self.webhook_url,
                error=str(e)
            )
            return {'success': 0, 'failed': len(events)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check webhook endpoint health."""
        try:
            # Try a HEAD request to check connectivity
            r = await self.client.head(self.webhook_url, timeout=3.0)
            
            return {
                'status': 'healthy' if r.status_code < 500 else 'degraded',
                'integration': self.name,
                'backend': 'webhook',
                'url': self.webhook_url,
                'response_code': r.status_code
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'integration': self.name,
                'backend': 'webhook',
                'url': self.webhook_url,
                'error': str(e)
            }
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
        logger.info("webhook_integration_closed", name=self.name)

