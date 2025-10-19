"""Base integration interface and configuration."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class IntegrationType(str, Enum):
    """Types of integrations."""
    LOCAL_API = "local_api"
    ZABBIX = "zabbix"
    ELK = "elk"
    CSV = "csv"
    JSON = "json"
    WEBHOOK = "webhook"
    AWS_CLOUDWATCH = "aws_cloudwatch"
    AWS_XRAY = "aws_xray"


@dataclass
class IntegrationConfig:
    """Configuration for an integration."""
    enabled: bool = True
    type: IntegrationType = IntegrationType.LOCAL_API
    name: str = "default"
    config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}


class BaseIntegration(ABC):
    """
    Abstract base class for all integrations.
    
    All integration adapters must implement this interface.
    """
    
    def __init__(self, config: IntegrationConfig):
        """
        Initialize the integration.
        
        Args:
            config: Integration configuration
        """
        self.config = config
        self.name = config.name
        self.enabled = config.enabled
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the integration (connect, setup, etc.).
        
        Called once during startup.
        """
        pass
    
    @abstractmethod
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """
        Send a single event to the integration backend.
        
        Args:
            event: Event dictionary to send
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Send a batch of events to the integration backend.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            Dictionary with 'success' and 'failed' counts
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the integration.
        
        Returns:
            Dictionary with health status information
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """
        Close the integration and cleanup resources.
        
        Called during shutdown.
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if integration is enabled."""
        return self.enabled
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.config.get(key, default)

