"""
Elasticsearch adapter for reading monitoring events from ELK stack.
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from elasticsearch import AsyncElasticsearch
import os

from .base import DataAdapter, AdapterResult

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class ELKAdapter(DataAdapter):
    """
    Adapter for reading events from Elasticsearch (ELK stack).
    Events are indexed in Elasticsearch by the monitoring system.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.hosts = config.get("hosts", ["http://localhost:9200"])
        self.index_pattern = config.get("index_pattern", "monitoring-events-*")
        self.api_key = config.get("api_key", os.getenv("ELASTIC_API_KEY"))
        self.http_auth = config.get("http_auth")
        self.use_ssl = config.get("use_ssl", False)
        self.verify_certs = config.get("verify_certs", False)
        
        self.client: Optional[AsyncElasticsearch] = None
    
    async def initialize(self) -> None:
        """Initialize Elasticsearch client."""
        try:
            self.client = AsyncElasticsearch(
                hosts=self.hosts,
                api_key=self.api_key,
                http_auth=self.http_auth,
                use_ssl=self.use_ssl,
                verify_certs=self.verify_certs,
                max_retries=3,
                timeout=10,
                retry_on_timeout=True
            )
            logger.info("ELK adapter initialized", adapter=self.name, hosts=self.hosts)
        except Exception as e:
            logger.error("Failed to initialize ELK adapter", adapter=self.name, error=str(e))
            raise
    
    async def close(self) -> None:
        """Close Elasticsearch client."""
        if self.client:
            await self.client.close()
            logger.info("ELK adapter closed", adapter=self.name)
    
    async def query_events(
        self,
        filters: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> AdapterResult:
        """Query events from Elasticsearch."""
        if not self.client:
            return AdapterResult(
                success=False,
                data=[],
                source=self.name,
                count=0,
                error="Adapter not initialized"
            )
        
        start = time.time()
        
        try:
            # Build Elasticsearch query
            query = {"bool": {"must": []}}
            
            # Add filters
            if filters:
                if 'site_id' in filters:
                    query["bool"]["must"].append({"term": {"site_id.keyword": filters['site_id']}})
                if 'app_name' in filters:
                    query["bool"]["must"].append({"term": {"app_name.keyword": filters['app_name']}})
                if 'entity_id' in filters:
                    query["bool"]["must"].append({"term": {"entity_id.keyword": filters['entity_id']}})
                if 'event_kind' in filters:
                    query["bool"]["must"].append({"term": {"event_kind": filters['event_kind']}})
            
            # Add time range
            if start_time or end_time:
                time_range = {}
                if start_time:
                    time_range["gte"] = start_time.isoformat()
                if end_time:
                    time_range["lte"] = end_time.isoformat()
                query["bool"]["must"].append({"range": {"timestamp": time_range}})
            
            # Build search request
            search_body = {
                "query": query,
                "sort": [{"timestamp": {"order": "desc"}}],
                "from": offset,
                "size": limit
            }
            
            # Execute search
            response = await self.client.search(
                index=self.index_pattern,
                body=search_body
            )
            
            # Extract events from hits
            events = []
            if 'hits' in response and 'hits' in response['hits']:
                for hit in response['hits']['hits']:
                    event = hit['_source']
                    event['_id'] = hit['_id']  # Include ES document ID
                    events.append(event)
            
            query_time = (time.time() - start) * 1000
            
            logger.debug("ELK query completed",
                        adapter=self.name,
                        count=len(events),
                        total=response['hits']['total']['value'],
                        query_time_ms=query_time)
            
            return AdapterResult(
                success=True,
                data=events,
                source=self.name,
                count=len(events),
                query_time_ms=query_time
            )
            
        except Exception as e:
            query_time = (time.time() - start) * 1000
            logger.error("ELK query failed", adapter=self.name, error=str(e))
            return AdapterResult(
                success=False,
                data=[],
                source=self.name,
                count=0,
                error=str(e),
                query_time_ms=query_time
            )
    
    async def health_check(self) -> bool:
        """Check if Elasticsearch is accessible."""
        if not self.client:
            return False
        
        try:
            info = await self.client.info()
            logger.debug("ELK health check passed", 
                        adapter=self.name, 
                        version=info.get('version', {}).get('number'))
            return True
        except Exception as e:
            logger.warning("ELK health check failed", adapter=self.name, error=str(e))
            return False

