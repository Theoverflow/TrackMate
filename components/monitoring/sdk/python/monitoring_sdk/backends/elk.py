"""ELK backend - sends events to Elasticsearch/Loki."""

from typing import Dict, Any, List
from datetime import datetime

from .base import Backend, BackendResult, BackendStatus

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from elasticsearch import Elasticsearch, helpers
    from elasticsearch.exceptions import ElasticsearchException
    HAS_ELASTICSEARCH = True
except ImportError:
    HAS_ELASTICSEARCH = False
    logger.warning("elasticsearch not installed, ELKBackend will not work")


class ELKBackend(Backend):
    """
    ELK (Elasticsearch) backend implementation.
    
    Sends events to Elasticsearch for indexing and search.
    
    Configuration:
        url: Elasticsearch URL (default: http://localhost:9200)
        index: Index name (default: monitoring)
        username: Basic auth username (optional)
        password: Basic auth password (optional)
        api_key: API key authentication (optional)
        verify_certs: Verify SSL certificates (default: True)
        batch_size: Number of events to batch before sending (default: 50)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        if not HAS_ELASTICSEARCH:
            raise ImportError(
                "elasticsearch is required for ELKBackend. "
                "Install with: pip install elasticsearch"
            )
        
        self.url = config.get('url', 'http://localhost:9200')
        self.index = config.get('index', 'monitoring')
        self.username = config.get('username')
        self.password = config.get('password')
        self.api_key = config.get('api_key')
        self.verify_certs = config.get('verify_certs', True)
        self.batch_size = config.get('batch_size', 50)
        self._es_client = None
        self._pending_events = []
    
    def initialize(self) -> None:
        """Initialize Elasticsearch client."""
        es_config = {
            'hosts': [self.url],
            'verify_certs': self.verify_certs
        }
        
        if self.api_key:
            es_config['api_key'] = self.api_key
        elif self.username and self.password:
            es_config['basic_auth'] = (self.username, self.password)
        
        self._es_client = Elasticsearch(**es_config)
        
        # Verify connection
        if not self._es_client.ping():
            raise ConnectionError(f"Cannot connect to Elasticsearch at {self.url}")
        
        # Create index if it doesn't exist
        if not self._es_client.indices.exists(index=self.index):
            self._es_client.indices.create(
                index=self.index,
                body={
                    'mappings': {
                        'properties': {
                            'timestamp': {'type': 'date'},
                            'site_id': {'type': 'keyword'},
                            'app_name': {'type': 'keyword'},
                            'event_kind': {'type': 'keyword'},
                            'entity_type': {'type': 'keyword'},
                            'metrics': {'type': 'object'},
                            'metadata': {'type': 'object'}
                        }
                    }
                }
            )
        
        self._initialized = True
        logger.info("elk_backend_initialized", url=self.url, index=self.index)
    
    def _bulk_index(self, events: List[Dict[str, Any]]) -> BackendResult:
        """Bulk index events to Elasticsearch."""
        try:
            # Prepare bulk actions
            actions = []
            for event in events:
                action = {
                    '_index': self.index,
                    '_source': event
                }
                actions.append(action)
            
            # Bulk index
            success, failed = helpers.bulk(
                self._es_client,
                actions,
                raise_on_error=False,
                raise_on_exception=False
            )
            
            if failed:
                logger.warning("elk_partial_success", success=success, failed=failed)
                return BackendResult(
                    status=BackendStatus.PARTIAL,
                    message=f"Indexed {success} events, {failed} failed",
                    events_sent=success,
                    events_failed=failed
                )
            
            logger.debug("events_indexed_to_elk", count=success)
            
            return BackendResult(
                status=BackendStatus.SUCCESS,
                message=f"Indexed {success} events to Elasticsearch",
                events_sent=success
            )
        
        except ElasticsearchException as e:
            logger.error(
                "elk_index_failed",
                error=str(e),
                count=len(events)
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"Elasticsearch error: {str(e)}",
                events_failed=len(events),
                error=e
            )
        
        except Exception as e:
            logger.error(
                "elk_index_error",
                error=str(e),
                error_type=type(e).__name__
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"Error: {str(e)}",
                events_failed=len(events),
                error=e
            )
    
    def send_event(self, event: Dict[str, Any]) -> BackendResult:
        """
        Queue event for Elasticsearch indexing (batched).
        
        Args:
            event: Event dictionary
            
        Returns:
            BackendResult with operation status
        """
        if not self._initialized:
            self.initialize()
        
        self._pending_events.append(event)
        
        # Index if batch is full
        if len(self._pending_events) >= self.batch_size:
            result = self._bulk_index(self._pending_events)
            self._pending_events = []
            return result
        
        return BackendResult(
            status=BackendStatus.SUCCESS,
            message="Event queued for indexing",
            events_sent=1
        )
    
    def send_batch(self, events: List[Dict[str, Any]]) -> BackendResult:
        """
        Index a batch of events to Elasticsearch.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            BackendResult with operation status
        """
        if not self._initialized:
            self.initialize()
        
        # Index pending events first
        if self._pending_events:
            self._bulk_index(self._pending_events)
            self._pending_events = []
        
        # Index batch
        return self._bulk_index(events)
    
    def health_check(self) -> bool:
        """Check if Elasticsearch is reachable."""
        if not self._initialized:
            return False
        
        try:
            return self._es_client.ping()
        except Exception:
            return False
    
    def close(self) -> None:
        """Flush pending events and close."""
        if self._pending_events:
            self._bulk_index(self._pending_events)
            self._pending_events = []
        
        if self._es_client:
            self._es_client.close()
        
        self._initialized = False
        logger.info("elk_backend_closed")

