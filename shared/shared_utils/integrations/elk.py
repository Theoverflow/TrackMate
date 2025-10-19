"""Elasticsearch/ELK integration."""
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


class ELKIntegration(BaseIntegration):
    """
    Integration with Elasticsearch/ELK stack.
    
    Sends events directly to Elasticsearch for indexing and Kibana visualization.
    
    Configuration:
        - elasticsearch_url: Elasticsearch URL (e.g., http://elasticsearch:9200)
        - index_prefix: Index name prefix (default: wafer-monitor)
        - username: Optional basic auth username
        - password: Optional basic auth password
        - api_key: Optional API key
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize ELK integration."""
        super().__init__(config)
        self.es_url = self.get_config('elasticsearch_url', 'http://localhost:9200')
        self.index_prefix = self.get_config('index_prefix', 'wafer-monitor')
        self.username = self.get_config('username')
        self.password = self.get_config('password')
        self.api_key = self.get_config('api_key')
        self.client: httpx.AsyncClient = None
    
    async def initialize(self) -> None:
        """Initialize Elasticsearch client."""
        headers = {'Content-Type': 'application/json'}
        auth = None
        
        if self.api_key:
            headers['Authorization'] = f'ApiKey {self.api_key}'
        elif self.username and self.password:
            auth = (self.username, self.password)
        
        self.client = httpx.AsyncClient(
            timeout=10.0,
            headers=headers,
            auth=auth
        )
        
        # Create index template if it doesn't exist
        await self._create_index_template()
        
        self._initialized = True
        logger.info(
            "elk_integration_initialized",
            name=self.name,
            es_url=self.es_url,
            index_prefix=self.index_prefix
        )
    
    async def _create_index_template(self) -> None:
        """Create Elasticsearch index template for wafer monitoring data."""
        template = {
            'index_patterns': [f'{self.index_prefix}-*'],
            'mappings': {
                'properties': {
                    'timestamp': {'type': 'date'},
                    'site_id': {'type': 'keyword'},
                    'app_name': {'type': 'keyword'},
                    'app_version': {'type': 'keyword'},
                    'entity_type': {'type': 'keyword'},
                    'entity_id': {'type': 'keyword'},
                    'event_kind': {'type': 'keyword'},
                    'status': {'type': 'keyword'},
                    'duration_s': {'type': 'float'},
                    'cpu_user_s': {'type': 'float'},
                    'cpu_system_s': {'type': 'float'},
                    'mem_max_mb': {'type': 'float'},
                    'business_key': {'type': 'keyword'},
                    'metadata': {'type': 'object', 'enabled': True}
                }
            },
            'settings': {
                'number_of_shards': 1,
                'number_of_replicas': 1,
                'index.lifecycle.name': 'wafer-monitor-policy',
                'index.lifecycle.rollover_alias': f'{self.index_prefix}-alias'
            }
        }
        
        try:
            r = await self.client.put(
                f'{self.es_url}/_index_template/{self.index_prefix}-template',
                json=template
            )
            if r.status_code in (200, 201):
                logger.info("elasticsearch_template_created")
        except Exception as e:
            logger.warning("elasticsearch_template_creation_failed", error=str(e))
    
    def _event_to_es_document(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert monitoring event to Elasticsearch document.
        
        Args:
            event: Monitoring event
            
        Returns:
            Elasticsearch document
        """
        entity = event.get('entity', {})
        event_data = event.get('event', {})
        metrics = event_data.get('metrics', {})
        app = event.get('app', {})
        
        return {
            'timestamp': event_data.get('at'),
            'idempotency_key': event.get('idempotency_key'),
            'site_id': event.get('site_id'),
            'app_name': app.get('name'),
            'app_version': app.get('version'),
            'app_id': app.get('app_id'),
            'entity_type': entity.get('type'),
            'entity_id': entity.get('id'),
            'parent_id': entity.get('parent_id'),
            'business_key': entity.get('business_key'),
            'sub_key': entity.get('sub_key'),
            'event_kind': event_data.get('kind'),
            'status': event_data.get('status'),
            'duration_s': metrics.get('duration_s'),
            'cpu_user_s': metrics.get('cpu_user_s'),
            'cpu_system_s': metrics.get('cpu_system_s'),
            'mem_max_mb': metrics.get('mem_max_mb'),
            'metadata': event_data.get('metadata', {})
        }
    
    def _get_index_name(self) -> str:
        """Get current index name with date suffix."""
        today = datetime.utcnow().strftime('%Y.%m.%d')
        return f'{self.index_prefix}-{today}'
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """Send event to Elasticsearch."""
        try:
            doc = self._event_to_es_document(event)
            index_name = self._get_index_name()
            
            r = await self.client.post(
                f'{self.es_url}/{index_name}/_doc',
                json=doc
            )
            
            if r.status_code in (200, 201):
                logger.debug("event_sent_to_elasticsearch", index=index_name)
                return True
            else:
                logger.warning("elasticsearch_index_failed", status=r.status_code)
                return False
        except Exception as e:
            logger.error("elasticsearch_send_failed", error=str(e))
            return False
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Send batch of events to Elasticsearch using bulk API."""
        try:
            index_name = self._get_index_name()
            
            # Build bulk request
            bulk_data = []
            for event in events:
                # Action line
                bulk_data.append(json.dumps({'index': {'_index': index_name}}))
                # Document line
                bulk_data.append(json.dumps(self._event_to_es_document(event)))
            
            bulk_body = '\n'.join(bulk_data) + '\n'
            
            r = await self.client.post(
                f'{self.es_url}/_bulk',
                content=bulk_body,
                headers={'Content-Type': 'application/x-ndjson'}
            )
            
            if r.status_code == 200:
                result = r.json()
                items = result.get('items', [])
                
                success = sum(1 for item in items if item.get('index', {}).get('status') in (200, 201))
                failed = len(items) - success
                
                logger.info(
                    "batch_sent_to_elasticsearch",
                    total=len(events),
                    success=success,
                    failed=failed
                )
                return {'success': success, 'failed': failed}
            else:
                logger.error("elasticsearch_bulk_failed", status=r.status_code)
                return {'success': 0, 'failed': len(events)}
        except Exception as e:
            logger.error("elasticsearch_batch_error", error=str(e))
            return {'success': 0, 'failed': len(events)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Elasticsearch health."""
        try:
            r = await self.client.get(f'{self.es_url}/_cluster/health', timeout=3.0)
            
            if r.status_code == 200:
                health = r.json()
                status = health.get('status', 'unknown')
                
                return {
                    'status': 'healthy' if status == 'green' else 'degraded',
                    'integration': self.name,
                    'backend': 'elasticsearch',
                    'cluster_status': status,
                    'details': health
                }
            else:
                return {
                    'status': 'unhealthy',
                    'integration': self.name,
                    'backend': 'elasticsearch',
                    'error': f'HTTP {r.status_code}'
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'integration': self.name,
                'backend': 'elasticsearch',
                'error': str(e)
            }
    
    async def close(self) -> None:
        """Close Elasticsearch client."""
        if self.client:
            await self.client.aclose()
        logger.info("elk_integration_closed", name=self.name)

