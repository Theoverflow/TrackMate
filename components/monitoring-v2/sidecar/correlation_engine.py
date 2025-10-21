"""
Correlation Engine
Buffers and correlates messages from multiple sources
"""

import asyncio
import logging
from typing import Dict, List, Callable
from collections import defaultdict
from datetime import datetime

import sys
sys.path.insert(0, str(__file__ + '/../../'))
from protocol.messages import Message

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """
    Buffers messages and flushes them to routing engine
    
    Handles:
    - Per-source buffering
    - Batch flushing (by size or time)
    - Trace correlation (future enhancement)
    """
    
    def __init__(self, on_flush: Callable, flush_batch_size: int = 100, 
                 flush_interval: int = 5):
        self.on_flush = on_flush
        self.flush_batch_size = flush_batch_size
        self.flush_interval = flush_interval
        
        # Buffers
        self.buffers: Dict[str, List[Message]] = defaultdict(list)
        self.buffer_timestamps: Dict[str, datetime] = {}
        
        # Trace store (for correlation)
        self.traces: Dict[str, List[Message]] = defaultdict(list)
        
        # Statistics
        self.messages_received = 0
        self.messages_flushed = 0
        self.flush_count = 0
        
        # Background task
        self.running = False
        self.flush_task = None
        
        logger.info(f"Correlation engine initialized " +
                   f"(batch={flush_batch_size}, interval={flush_interval}s)")
    
    async def start(self):
        """Start background flush task"""
        self.running = True
        self.flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("Correlation engine started")
    
    async def stop(self):
        """Stop and flush all pending messages"""
        logger.info("Stopping correlation engine...")
        self.running = False
        
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush all remaining messages
        await self.flush_all()
        logger.info("Correlation engine stopped")
    
    async def process_message(self, message: Message):
        """Process incoming message"""
        self.messages_received += 1
        
        # Add to source buffer
        source = message.src
        self.buffers[source].append(message)
        
        # Track buffer timestamp
        if source not in self.buffer_timestamps:
            self.buffer_timestamps[source] = datetime.now()
        
        # Add to trace store if trace_id present
        if message.tid:
            self.traces[message.tid].append(message)
        
        # Check if buffer should be flushed
        if len(self.buffers[source]) >= self.flush_batch_size:
            await self._flush_source(source)
    
    async def _periodic_flush(self):
        """Periodically flush buffers based on time"""
        while self.running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_by_time()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}", exc_info=True)
    
    async def _flush_by_time(self):
        """Flush buffers that have exceeded time threshold"""
        now = datetime.now()
        sources_to_flush = []
        
        for source, timestamp in self.buffer_timestamps.items():
            age = (now - timestamp).total_seconds()
            if age >= self.flush_interval and self.buffers[source]:
                sources_to_flush.append(source)
        
        # Flush each source
        for source in sources_to_flush:
            await self._flush_source(source)
    
    async def _flush_source(self, source: str):
        """Flush messages for a specific source"""
        if not self.buffers[source]:
            return
        
        messages = self.buffers[source]
        self.buffers[source] = []
        del self.buffer_timestamps[source]
        
        self.messages_flushed += len(messages)
        self.flush_count += 1
        
        logger.debug(f"Flushing {len(messages)} messages from '{source}'")
        
        try:
            await self.on_flush(messages)
        except Exception as e:
            logger.error(f"Error flushing messages: {e}", exc_info=True)
    
    async def flush_all(self):
        """Flush all pending messages"""
        sources = list(self.buffers.keys())
        for source in sources:
            await self._flush_source(source)
        
        logger.info(f"Flushed all buffers ({len(sources)} sources)")
    
    def get_trace(self, trace_id: str) -> List[Message]:
        """Get all messages for a trace ID"""
        return self.traces.get(trace_id, [])
    
    def get_stats(self) -> dict:
        """Get correlation engine statistics"""
        buffer_sizes = {
            source: len(msgs) for source, msgs in self.buffers.items()
        }
        
        return {
            'messages_received': self.messages_received,
            'messages_flushed': self.messages_flushed,
            'flush_count': self.flush_count,
            'buffer_sizes': buffer_sizes,
            'total_buffered': sum(buffer_sizes.values()),
            'trace_count': len(self.traces)
        }

