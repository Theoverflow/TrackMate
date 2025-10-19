"""Dependency injection container for integrations."""
import os
import json
from typing import Dict, List, Optional, Type
from .base import BaseIntegration, IntegrationConfig, IntegrationType
from .local_api import LocalAPIIntegration
from .zabbix import ZabbixIntegration
from .elk import ELKIntegration
from .csv_export import CSVExportIntegration
from .json_export import JSONExportIntegration
from .webhook import WebhookIntegration
from .aws_cloudwatch import AWSCloudWatchIntegration
from .aws_xray import AWSXRayIntegration

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class IntegrationContainer:
    """
    Dependency injection container for managing integrations.
    
    Supports:
    - Multiple active integrations
    - Configuration from environment or code
    - Lifecycle management (init, close)
    - Health checks across all integrations
    """
    
    # Registry of available integration classes
    INTEGRATION_REGISTRY: Dict[IntegrationType, Type[BaseIntegration]] = {
        IntegrationType.LOCAL_API: LocalAPIIntegration,
        IntegrationType.ZABBIX: ZabbixIntegration,
        IntegrationType.ELK: ELKIntegration,
        IntegrationType.CSV: CSVExportIntegration,
        IntegrationType.JSON: JSONExportIntegration,
        IntegrationType.WEBHOOK: WebhookIntegration,
        IntegrationType.AWS_CLOUDWATCH: AWSCloudWatchIntegration,
        IntegrationType.AWS_XRAY: AWSXRayIntegration,
    }
    
    def __init__(self):
        """Initialize the container."""
        self.integrations: Dict[str, BaseIntegration] = {}
        self._initialized = False
    
    def register(self, config: IntegrationConfig) -> None:
        """
        Register an integration.
        
        Args:
            config: Integration configuration
        """
        if config.name in self.integrations:
            logger.warning(
                "integration_already_registered",
                name=config.name,
                type=config.type
            )
            return
        
        integration_class = self.INTEGRATION_REGISTRY.get(config.type)
        if not integration_class:
            logger.error(
                "unknown_integration_type",
                type=config.type,
                available=list(self.INTEGRATION_REGISTRY.keys())
            )
            return
        
        integration = integration_class(config)
        self.integrations[config.name] = integration
        
        logger.info(
            "integration_registered",
            name=config.name,
            type=config.type,
            enabled=config.enabled
        )
    
    def register_from_env(self) -> None:
        """
        Register integrations from environment variables.
        
        Expected format:
            INTEGRATIONS_CONFIG='[
                {
                    "type": "local_api",
                    "name": "primary",
                    "enabled": true,
                    "config": {"base_url": "http://localhost:18000"}
                },
                {
                    "type": "zabbix",
                    "name": "zabbix-prod",
                    "enabled": true,
                    "config": {"zabbix_server": "http://zabbix:10051", "host": "wafer-monitor"}
                }
            ]'
        """
        config_json = os.getenv('INTEGRATIONS_CONFIG')
        if not config_json:
            # Fallback to default Local API integration
            logger.info("no_integrations_config_using_default")
            self.register(IntegrationConfig(
                type=IntegrationType.LOCAL_API,
                name='default',
                enabled=True,
                config={
                    'base_url': os.getenv('LOCAL_API_BASE', 'http://localhost:18000'),
                    'timeout': float(os.getenv('LOCAL_API_TIMEOUT', '5.0'))
                }
            ))
            return
        
        try:
            configs = json.loads(config_json)
            for cfg_dict in configs:
                config = IntegrationConfig(
                    type=IntegrationType(cfg_dict.get('type')),
                    name=cfg_dict.get('name', 'unnamed'),
                    enabled=cfg_dict.get('enabled', True),
                    config=cfg_dict.get('config', {})
                )
                self.register(config)
        except Exception as e:
            logger.error("failed_to_load_integrations_config", error=str(e))
    
    async def initialize_all(self) -> None:
        """Initialize all registered integrations."""
        logger.info("initializing_integrations", count=len(self.integrations))
        
        for name, integration in self.integrations.items():
            if not integration.is_enabled():
                logger.info("skipping_disabled_integration", name=name)
                continue
            
            try:
                await integration.initialize()
                logger.info("integration_initialized", name=name)
            except Exception as e:
                logger.error(
                    "integration_initialization_failed",
                    name=name,
                    error=str(e)
                )
        
        self._initialized = True
        logger.info("all_integrations_initialized")
    
    async def send_event(self, event: Dict) -> Dict[str, bool]:
        """
        Send event to all enabled integrations.
        
        Args:
            event: Event dictionary
            
        Returns:
            Dictionary mapping integration name to success status
        """
        results = {}
        
        for name, integration in self.integrations.items():
            if not integration.is_enabled():
                continue
            
            try:
                success = await integration.send_event(event)
                results[name] = success
            except Exception as e:
                logger.error(
                    "integration_send_failed",
                    integration=name,
                    error=str(e)
                )
                results[name] = False
        
        return results
    
    async def send_batch(self, events: List[Dict]) -> Dict[str, Dict[str, int]]:
        """
        Send batch of events to all enabled integrations.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            Dictionary mapping integration name to result stats
        """
        results = {}
        
        for name, integration in self.integrations.items():
            if not integration.is_enabled():
                continue
            
            try:
                result = await integration.send_batch(events)
                results[name] = result
            except Exception as e:
                logger.error(
                    "integration_batch_failed",
                    integration=name,
                    error=str(e)
                )
                results[name] = {'success': 0, 'failed': len(events)}
        
        return results
    
    async def health_check_all(self) -> Dict[str, Dict]:
        """
        Run health checks on all integrations.
        
        Returns:
            Dictionary mapping integration name to health status
        """
        results = {}
        
        for name, integration in self.integrations.items():
            try:
                health = await integration.health_check()
                results[name] = health
            except Exception as e:
                results[name] = {
                    'status': 'error',
                    'integration': name,
                    'error': str(e)
                }
        
        return results
    
    async def close_all(self) -> None:
        """Close all integrations and cleanup resources."""
        logger.info("closing_integrations", count=len(self.integrations))
        
        for name, integration in self.integrations.items():
            try:
                await integration.close()
                logger.info("integration_closed", name=name)
            except Exception as e:
                logger.error(
                    "integration_close_failed",
                    name=name,
                    error=str(e)
                )
        
        self.integrations.clear()
        self._initialized = False
        logger.info("all_integrations_closed")
    
    def get_integration(self, name: str) -> Optional[BaseIntegration]:
        """Get integration by name."""
        return self.integrations.get(name)
    
    def list_integrations(self) -> List[str]:
        """List all registered integration names."""
        return list(self.integrations.keys())
    
    def get_enabled_integrations(self) -> List[str]:
        """List enabled integration names."""
        return [
            name for name, integration in self.integrations.items()
            if integration.is_enabled()
        ]


# Global container instance
_container: Optional[IntegrationContainer] = None


def get_container() -> IntegrationContainer:
    """Get or create the global integration container."""
    global _container
    if _container is None:
        _container = IntegrationContainer()
    return _container

