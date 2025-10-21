"""
Base Backend Interface
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
import sys
sys.path.insert(0, str(__file__ + '/../../../'))

from protocol.messages import Message


@dataclass
class BackendResult:
    """Result of backend send operation"""
    success: bool
    messages_sent: int
    error: Optional[str] = None
    latency_ms: float = 0.0


class BaseBackend(ABC):
    """Base class for all backend adapters"""
    
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.messages_sent = 0
        self.messages_failed = 0
        self.total_latency_ms = 0.0
    
    @abstractmethod
    async def send(self, messages: List[Message]) -> BackendResult:
        """
        Send messages to backend
        
        Args:
            messages: List of messages to send
        
        Returns:
            BackendResult with status
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Close backend connections"""
        pass
    
    def get_stats(self) -> dict:
        """Get backend statistics"""
        avg_latency = (self.total_latency_ms / self.messages_sent 
                      if self.messages_sent > 0 else 0)
        
        return {
            'name': self.name,
            'messages_sent': self.messages_sent,
            'messages_failed': self.messages_failed,
            'avg_latency_ms': round(avg_latency, 2)
        }
    
    def _update_stats(self, result: BackendResult):
        """Update internal statistics"""
        if result.success:
            self.messages_sent += result.messages_sent
            self.total_latency_ms += result.latency_ms
        else:
            self.messages_failed += result.messages_sent

