"""Zabbix integration for monitoring."""
import httpx
import json
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseIntegration, IntegrationConfig

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class ZabbixIntegration(BaseIntegration):
    """
    Integration with Zabbix monitoring system.
    
    Sends events as Zabbix trapper items.
    
    Configuration:
        - zabbix_server: Zabbix server URL (e.g., http://zabbix:10051)
        - host: Zabbix host name
        - auth_token: Optional authentication token
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize Zabbix integration."""
        super().__init__(config)
        self.zabbix_server = self.get_config('zabbix_server', 'http://localhost:10051')
        self.host = self.get_config('host', 'wafer-monitor')
        self.auth_token = self.get_config('auth_token')
        self.client: httpx.AsyncClient = None
    
    async def initialize(self) -> None:
        """Initialize Zabbix client."""
        self.client = httpx.AsyncClient(
            timeout=10.0,
            headers={'Content-Type': 'application/json'}
        )
        self._initialized = True
        logger.info(
            "zabbix_integration_initialized",
            name=self.name,
            server=self.zabbix_server,
            host=self.host
        )
    
    def _event_to_zabbix_item(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert monitoring event to Zabbix trapper item.
        
        Args:
            event: Monitoring event
            
        Returns:
            Zabbix trapper item format
        """
        entity = event.get('entity', {})
        event_data = event.get('event', {})
        metrics = event_data.get('metrics', {})
        
        # Create Zabbix item key
        entity_type = entity.get('type', 'unknown')
        event_kind = event_data.get('kind', 'unknown')
        key = f"wafer.{entity_type}.{event_kind}"
        
        # Prepare value (use duration_s if available, otherwise 1)
        value = metrics.get('duration_s', 1)
        
        # Timestamp
        timestamp = int(datetime.fromisoformat(
            event_data.get('at', datetime.utcnow().isoformat())
        ).timestamp())
        
        return {
            'host': self.host,
            'key': key,
            'value': value,
            'clock': timestamp,
            'ns': 0
        }
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """Send event to Zabbix as trapper item."""
        try:
            item = self._event_to_zabbix_item(event)
            
            # Zabbix sender protocol
            payload = {
                'request': 'sender data',
                'data': [item]
            }
            
            # Send to Zabbix trapper
            r = await self.client.post(
                f"{self.zabbix_server}/zabbix_sender",
                json=payload
            )
            
            if r.status_code == 200:
                logger.debug("event_sent_to_zabbix", key=item['key'])
                return True
            else:
                logger.warning(
                    "zabbix_send_non_200",
                    status_code=r.status_code,
                    response=r.text
                )
                return False
        except Exception as e:
            logger.error("zabbix_send_failed", error=str(e))
            return False
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Send batch of events to Zabbix."""
        items = [self._event_to_zabbix_item(e) for e in events]
        
        try:
            payload = {
                'request': 'sender data',
                'data': items
            }
            
            r = await self.client.post(
                f"{self.zabbix_server}/zabbix_sender",
                json=payload
            )
            
            if r.status_code == 200:
                result = r.json()
                processed = result.get('processed', len(items))
                failed = result.get('failed', 0)
                
                logger.info(
                    "batch_sent_to_zabbix",
                    total=len(items),
                    processed=processed,
                    failed=failed
                )
                return {'success': processed, 'failed': failed}
            else:
                logger.error("zabbix_batch_failed", status_code=r.status_code)
                return {'success': 0, 'failed': len(items)}
        except Exception as e:
            logger.error("zabbix_batch_error", error=str(e))
            return {'success': 0, 'failed': len(items)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Zabbix connectivity."""
        try:
            # Try to ping Zabbix API
            r = await self.client.get(f"{self.zabbix_server}/api_jsonrpc.php", timeout=3.0)
            
            return {
                'status': 'healthy' if r.status_code < 500 else 'degraded',
                'integration': self.name,
                'backend': 'zabbix',
                'server': self.zabbix_server,
                'host': self.host
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'integration': self.name,
                'backend': 'zabbix',
                'error': str(e)
            }
    
    async def close(self) -> None:
        """Close Zabbix client."""
        if self.client:
            await self.client.aclose()
        logger.info("zabbix_integration_closed", name=self.name)

