"""
Routing Engine
Routes messages to backends based on configuration
"""

import asyncio
import logging
from typing import List, Dict
from collections import defaultdict
from datetime import datetime

from .config import SidecarConfig, RoutingRule
from .backends.base import BaseBackend
from .backends.filesystem import FileSystemBackend
from .backends.timescaledb import TimescaleDBBackend

import sys
sys.path.insert(0, str(__file__ + '/../../'))
from protocol.messages import Message

logger = logging.getLogger(__name__)


class RoutingEngine:
    """
    Routes messages to configured backends based on rules
    """
    
    def __init__(self, config: SidecarConfig):
        self.config = config
        self.backends: Dict[str, BaseBackend] = {}
        self._initialize_backends()
    
    def _initialize_backends(self):
        """Initialize backend adapters from configuration"""
        for name, backend_config in self.config.backends.items():
            if not backend_config.enabled:
                logger.info(f"Backend '{name}' disabled, skipping")
                continue
            
            try:
                if backend_config.type == 'filesystem':
                    self.backends[name] = FileSystemBackend(name, backend_config.config)
                
                elif backend_config.type == 'timescaledb':
                    self.backends[name] = TimescaleDBBackend(name, backend_config.config)
                
                else:
                    logger.warning(f"Unknown backend type: {backend_config.type}")
            
            except Exception as e:
                logger.error(f"Failed to initialize backend '{name}': {e}", exc_info=True)
        
        logger.info(f"Initialized {len(self.backends)} backends: {list(self.backends.keys())}")
    
    async def route(self, messages: List[Message]):
        """
        Route messages to appropriate backends
        
        Messages are grouped by source and routed according to configuration
        """
        # Group messages by source
        by_source = defaultdict(list)
        for msg in messages:
            by_source[msg.src].append(msg)
        
        # Route each source's messages
        tasks = []
        for source, source_messages in by_source.items():
            task = self._route_source(source, source_messages)
            tasks.append(task)
        
        # Execute all routing tasks concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _route_source(self, source: str, messages: List[Message]):
        """Route messages from a specific source"""
        # Get routing rules for this source
        rules = self.config.get_routing_rules(source)
        
        if not rules:
            logger.warning(f"No routing rules for source '{source}', dropping {len(messages)} messages")
            return
        
        # Route to each configured backend
        tasks = []
        for rule in rules:
            if not rule.enabled:
                continue
            
            backend = self.backends.get(rule.backend)
            if not backend:
                logger.warning(f"Backend '{rule.backend}' not found for source '{source}'")
                continue
            
            # Apply filter if specified
            filtered_messages = self._apply_filter(messages, rule.filter)
            
            if filtered_messages:
                task = self._send_to_backend(backend, filtered_messages, source)
                tasks.append(task)
        
        # Send to all backends concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def _apply_filter(self, messages: List[Message], filter_spec: dict) -> List[Message]:
        """Apply filter to messages"""
        if not filter_spec:
            return messages
        
        filtered = []
        for msg in messages:
            # Filter by message types
            if 'types' in filter_spec:
                if msg.type in filter_spec['types']:
                    filtered.append(msg)
            else:
                filtered.append(msg)
        
        return filtered
    
    async def _send_to_backend(self, backend: BaseBackend, messages: List[Message], source: str):
        """Send messages to backend with error handling"""
        try:
            result = await backend.send(messages)
            
            if result.success:
                logger.debug(f"Sent {result.messages_sent} messages from '{source}' " +
                           f"to '{backend.name}' ({result.latency_ms:.2f}ms)")
            else:
                logger.error(f"Failed to send to '{backend.name}': {result.error}")
        
        except Exception as e:
            logger.error(f"Error sending to backend '{backend.name}': {e}", exc_info=True)
    
    async def close(self):
        """Close all backends"""
        logger.info("Closing all backends...")
        
        tasks = []
        for backend in self.backends.values():
            tasks.append(backend.close())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("All backends closed")
    
    def get_stats(self) -> dict:
        """Get routing engine statistics"""
        backend_stats = {}
        for name, backend in self.backends.items():
            backend_stats[name] = backend.get_stats()
        
        return {
            'backends': backend_stats,
            'routing_sources': list(self.config.routing.keys())
        }

