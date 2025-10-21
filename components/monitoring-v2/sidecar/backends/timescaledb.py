"""
TimescaleDB Backend
Stores messages in TimescaleDB (PostgreSQL with time-series extensions)
"""

import asyncpg
from typing import List
from datetime import datetime
import logging

from .base import BaseBackend, BackendResult
import sys
sys.path.insert(0, str(__file__ + '/../../../'))
from protocol.messages import Message

logger = logging.getLogger(__name__)


class TimescaleDBBackend(BaseBackend):
    """
    Stores messages in TimescaleDB
    """
    
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        
        self.connection_string = config['connection_string']
        self.table = config.get('table', 'monitoring_events')
        self.pool = None
        
        logger.info(f"TimescaleDB backend '{name}' initialized")
    
    async def _ensure_pool(self):
        """Ensure connection pool is created"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=2,
                max_size=10
            )
            logger.info(f"TimescaleDB connection pool created for '{self.name}'")
    
    async def send(self, messages: List[Message]) -> BackendResult:
        """Insert messages into TimescaleDB"""
        start_time = datetime.now()
        
        try:
            await self._ensure_pool()
            
            # Prepare batch insert
            records = []
            for msg in messages:
                # Convert timestamp to datetime
                ts_dt = datetime.fromtimestamp(msg.ts / 1000.0)
                
                records.append((
                    ts_dt,
                    msg.src,
                    msg.type,
                    msg.tid,
                    msg.sid,
                    msg.pid,
                    msg.data
                ))
            
            # Batch insert
            async with self.pool.acquire() as conn:
                await conn.executemany(
                    f"""
                    INSERT INTO {self.table} 
                    (timestamp, source, type, trace_id, span_id, parent_span_id, data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    records
                )
            
            # Calculate latency
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            result = BackendResult(
                success=True,
                messages_sent=len(messages),
                latency_ms=latency_ms
            )
            
            self._update_stats(result)
            logger.debug(f"Inserted {len(messages)} messages into TimescaleDB ({latency_ms:.2f}ms)")
            return result
            
        except Exception as e:
            logger.error(f"TimescaleDB backend error: {e}", exc_info=True)
            
            result = BackendResult(
                success=False,
                messages_sent=len(messages),
                error=str(e)
            )
            
            self._update_stats(result)
            return result
    
    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            logger.info(f"TimescaleDB backend '{self.name}' closed")


# SQL schema for TimescaleDB
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS monitoring_events (
    timestamp TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    trace_id TEXT,
    span_id TEXT,
    parent_span_id TEXT,
    data JSONB,
    PRIMARY KEY (timestamp, source, type)
);

-- Create hypertable (TimescaleDB specific)
SELECT create_hypertable('monitoring_events', 'timestamp', 
                        if_not_exists => TRUE,
                        chunk_time_interval => INTERVAL '1 day');

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_monitoring_source ON monitoring_events(source, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_monitoring_trace ON monitoring_events(trace_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_monitoring_type ON monitoring_events(type, timestamp DESC);
"""

