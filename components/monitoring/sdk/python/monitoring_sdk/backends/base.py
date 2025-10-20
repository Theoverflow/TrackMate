"""Base backend interface for Monitoring SDK."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class BackendStatus(str, Enum):
    """Backend operation status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class BackendResult:
    """Result of a backend operation."""
    status: BackendStatus
    message: str = ""
    events_sent: int = 0
    events_failed: int = 0
    error: Exception = None
    
    @property
    def success(self) -> bool:
        """Check if operation was successful."""
        return self.status == BackendStatus.SUCCESS
    
    @property
    def failed(self) -> bool:
        """Check if operation failed."""
        return self.status == BackendStatus.FAILED


class Backend(ABC):
    """
    Abstract base class for monitoring backends.
    
    All backend implementations must inherit from this class
    and implement the required methods.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the backend.
        
        Args:
            config: Backend-specific configuration
        """
        self.config = config
        self.enabled = config.get('enabled', True)
        self._initialized = False
    
    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the backend (connections, setup, etc.).
        
        Called once before first use.
        
        Raises:
            Exception: If initialization fails
        """
        pass
    
    @abstractmethod
    def send_event(self, event: Dict[str, Any]) -> BackendResult:
        """
        Send a single event to the backend.
        
        Args:
            event: Event dictionary
            
        Returns:
            BackendResult with operation status
        """
        pass
    
    @abstractmethod
    def send_batch(self, events: List[Dict[str, Any]]) -> BackendResult:
        """
        Send a batch of events to the backend.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            BackendResult with operation status
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """
        Close the backend and cleanup resources.
        
        Called during shutdown.
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if backend is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if backend is enabled."""
        return self.enabled
    
    def is_initialized(self) -> bool:
        """Check if backend is initialized."""
        return self._initialized
    
    def __enter__(self):
        """Context manager entry."""
        if not self._initialized:
            self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

