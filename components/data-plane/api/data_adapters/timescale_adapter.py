"""
TimescaleDB adapter for reading monitoring events from the managed database.
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncpg

from .base import DataAdapter, AdapterResult

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class TimescaleDBAdapter(DataAdapter):
    """
    Adapter for reading events from the managed TimescaleDB instance.
    This is the primary data source for events sent via the sidecar to Local API.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.connection_string = config.get("connection_string", "")
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self) -> None:
        """Initialize connection pool to TimescaleDB."""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=2,
                max_size=10,
                command_timeout=10.0
            )
            logger.info("TimescaleDB adapter initialized", adapter=self.name)
        except Exception as e:
            logger.error("Failed to initialize TimescaleDB adapter", adapter=self.name, error=str(e))
            raise
    
    async def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("TimescaleDB adapter closed", adapter=self.name)
    
    async def query_events(
        self,
        filters: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> AdapterResult:
        """Query events from TimescaleDB with filtering."""
        if not self.pool:
            return AdapterResult(
                success=False,
                data=[],
                source=self.name,
                count=0,
                error="Adapter not initialized"
            )
        
        start = time.time()
        
        try:
            # Build query
            query = """
                SELECT 
                    idempotency_key,
                    site_id,
                    app_name,
                    app_version,
                    entity_type,
                    entity_id,
                    event_kind,
                    occurred_at as timestamp,
                    status,
                    metrics,
                    metadata,
                    created_at
                FROM monitoring_events
                WHERE 1=1
            """
            
            params = []
            param_count = 1
            
            # Add filters
            if filters:
                if 'site_id' in filters:
                    query += f" AND site_id = ${param_count}"
                    params.append(filters['site_id'])
                    param_count += 1
                
                if 'app_name' in filters:
                    query += f" AND app_name = ${param_count}"
                    params.append(filters['app_name'])
                    param_count += 1
                
                if 'entity_id' in filters:
                    query += f" AND entity_id = ${param_count}"
                    params.append(filters['entity_id'])
                    param_count += 1
                
                if 'event_kind' in filters:
                    query += f" AND event_kind = ${param_count}"
                    params.append(filters['event_kind'])
                    param_count += 1
            
            # Add time range
            if start_time:
                query += f" AND occurred_at >= ${param_count}"
                params.append(start_time)
                param_count += 1
            
            if end_time:
                query += f" AND occurred_at <= ${param_count}"
                params.append(end_time)
                param_count += 1
            
            # Add ordering, limit, offset
            query += f" ORDER BY occurred_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
            params.extend([limit, offset])
            
            # Execute query
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
            
            # Convert to dictionaries
            events = []
            for row in rows:
                event = dict(row)
                # Convert timestamp to ISO string
                if 'timestamp' in event and isinstance(event['timestamp'], datetime):
                    event['timestamp'] = event['timestamp'].isoformat()
                if 'created_at' in event and isinstance(event['created_at'], datetime):
                    event['created_at'] = event['created_at'].isoformat()
                events.append(event)
            
            query_time = (time.time() - start) * 1000
            
            logger.debug("TimescaleDB query completed", 
                        adapter=self.name, 
                        count=len(events), 
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
            logger.error("TimescaleDB query failed", 
                        adapter=self.name, 
                        error=str(e))
            return AdapterResult(
                success=False,
                data=[],
                source=self.name,
                count=0,
                error=str(e),
                query_time_ms=query_time
            )
    
    async def health_check(self) -> bool:
        """Check if TimescaleDB is accessible."""
        if not self.pool:
            return False
        
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            logger.debug("TimescaleDB health check passed", adapter=self.name)
            return True
        except Exception as e:
            logger.warning("TimescaleDB health check failed", adapter=self.name, error=str(e))
            return False

