"""
Base interface for data adapters.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AdapterResult:
    """Result from a data adapter query."""
    success: bool
    data: List[Dict[str, Any]]
    source: str
    count: int
    error: Optional[str] = None
    query_time_ms: float = 0.0

class DataAdapter(ABC):
    """
    Abstract base class for data adapters.
    
    Each adapter is responsible for reading monitoring events from a specific
    source (TimescaleDB, S3, Elasticsearch, etc.).
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the adapter and its connections."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close connections and cleanup resources."""
        pass
    
    @abstractmethod
    async def query_events(
        self,
        filters: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> AdapterResult:
        """
        Query events with optional filtering.
        
        Args:
            filters: Dictionary of filters (site_id, app_name, etc.)
            start_time: Start timestamp for time range
            end_time: End timestamp for time range
            limit: Maximum number of events to return
            offset: Number of events to skip
            
        Returns:
            AdapterResult containing the queried events
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the adapter is healthy and can query data.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def get_source_name(self) -> str:
        """Returns the source name for this adapter."""
        return self.name

