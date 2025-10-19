"""Unit tests for integration system."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'apps'))

from shared_utils.integrations import (
    IntegrationContainer,
    IntegrationConfig,
    IntegrationType,
    LocalAPIIntegration,
    CSVExportIntegration,
    JSONExportIntegration
)


@pytest.mark.asyncio
class TestIntegrationContainer:
    """Test suite for IntegrationContainer."""
    
    async def test_container_initialization(self):
        """Test container can be initialized."""
        container = IntegrationContainer()
        assert len(container.integrations) == 0
        assert container._initialized is False
    
    async def test_register_integration(self):
        """Test registering an integration."""
        container = IntegrationContainer()
        
        config = IntegrationConfig(
            type=IntegrationType.LOCAL_API,
            name='test-integration',
            enabled=True,
            config={'base_url': 'http://test:18000'}
        )
        
        container.register(config)
        
        assert 'test-integration' in container.integrations
        assert isinstance(container.integrations['test-integration'], LocalAPIIntegration)
    
    async def test_register_multiple_integrations(self):
        """Test registering multiple integrations."""
        container = IntegrationContainer()
        
        configs = [
            IntegrationConfig(
                type=IntegrationType.LOCAL_API,
                name='local-api',
                enabled=True,
                config={'base_url': 'http://localhost:18000'}
            ),
            IntegrationConfig(
                type=IntegrationType.CSV,
                name='csv-export',
                enabled=True,
                config={'output_dir': '/tmp/test'}
            ),
            IntegrationConfig(
                type=IntegrationType.JSON,
                name='json-export',
                enabled=False,
                config={'output_dir': '/tmp/test'}
            )
        ]
        
        for config in configs:
            container.register(config)
        
        assert len(container.integrations) == 3
        assert len(container.get_enabled_integrations()) == 2
    
    async def test_send_event_to_all(self):
        """Test sending event to all integrations."""
        container = IntegrationContainer()
        
        # Mock integrations
        mock_integration1 = AsyncMock()
        mock_integration1.is_enabled.return_value = True
        mock_integration1.send_event.return_value = True
        
        mock_integration2 = AsyncMock()
        mock_integration2.is_enabled.return_value = True
        mock_integration2.send_event.return_value = True
        
        container.integrations['mock1'] = mock_integration1
        container.integrations['mock2'] = mock_integration2
        
        event = {'test': 'data'}
        results = await container.send_event(event)
        
        assert results == {'mock1': True, 'mock2': True}
        mock_integration1.send_event.assert_called_once_with(event)
        mock_integration2.send_event.assert_called_once_with(event)
    
    async def test_send_batch_to_all(self):
        """Test sending batch to all integrations."""
        container = IntegrationContainer()
        
        mock_integration = AsyncMock()
        mock_integration.is_enabled.return_value = True
        mock_integration.send_batch.return_value = {'success': 5, 'failed': 0}
        
        container.integrations['mock'] = mock_integration
        
        events = [{'test': i} for i in range(5)]
        results = await container.send_batch(events)
        
        assert results == {'mock': {'success': 5, 'failed': 0}}
        mock_integration.send_batch.assert_called_once_with(events)
    
    async def test_health_check_all(self):
        """Test health check on all integrations."""
        container = IntegrationContainer()
        
        mock_integration = AsyncMock()
        mock_integration.health_check.return_value = {
            'status': 'healthy',
            'integration': 'mock'
        }
        
        container.integrations['mock'] = mock_integration
        
        results = await container.health_check_all()
        
        assert 'mock' in results
        assert results['mock']['status'] == 'healthy'
    
    async def test_close_all(self):
        """Test closing all integrations."""
        container = IntegrationContainer()
        
        mock_integration1 = AsyncMock()
        mock_integration2 = AsyncMock()
        
        container.integrations['mock1'] = mock_integration1
        container.integrations['mock2'] = mock_integration2
        
        await container.close_all()
        
        mock_integration1.close.assert_called_once()
        mock_integration2.close.assert_called_once()
        assert len(container.integrations) == 0


@pytest.mark.asyncio
class TestLocalAPIIntegration:
    """Test suite for LocalAPIIntegration."""
    
    async def test_initialization(self):
        """Test Local API integration initialization."""
        config = IntegrationConfig(
            type=IntegrationType.LOCAL_API,
            name='test',
            enabled=True,
            config={'base_url': 'http://test:18000', 'timeout': 10.0}
        )
        
        integration = LocalAPIIntegration(config)
        
        assert integration.base_url == 'http://test:18000'
        assert integration.timeout == 10.0
        
        await integration.initialize()
        assert integration._initialized
        
        await integration.close()


@pytest.mark.asyncio
class TestCSVExportIntegration:
    """Test suite for CSVExportIntegration."""
    
    async def test_csv_export(self, tmp_path):
        """Test CSV export functionality."""
        config = IntegrationConfig(
            type=IntegrationType.CSV,
            name='test-csv',
            enabled=True,
            config={'output_dir': str(tmp_path), 'rotation': 'none'}
        )
        
        integration = CSVExportIntegration(config)
        await integration.initialize()
        
        # Test event
        event = {
            'idempotency_key': 'test-key',
            'site_id': 'test-site',
            'app': {'app_id': 'app-1', 'name': 'test-app', 'version': '1.0'},
            'entity': {'type': 'job', 'id': 'job-1', 'business_key': 'test'},
            'event': {
                'kind': 'finished',
                'at': '2025-10-19T12:00:00Z',
                'status': 'succeeded',
                'metrics': {'duration_s': 1.5},
                'metadata': {}
            }
        }
        
        success = await integration.send_event(event)
        assert success
        
        # Check file was created
        csv_files = list(tmp_path.glob('*.csv'))
        assert len(csv_files) > 0
        
        await integration.close()


@pytest.mark.asyncio
class TestJSONExportIntegration:
    """Test suite for JSONExportIntegration."""
    
    async def test_json_export(self, tmp_path):
        """Test JSON export functionality."""
        config = IntegrationConfig(
            type=IntegrationType.JSON,
            name='test-json',
            enabled=True,
            config={'output_dir': str(tmp_path), 'rotation': 'none', 'pretty_print': False}
        )
        
        integration = JSONExportIntegration(config)
        await integration.initialize()
        
        # Test event
        event = {
            'idempotency_key': 'test-key',
            'site_id': 'test-site',
            'app': {'app_id': 'app-1', 'name': 'test-app', 'version': '1.0'},
            'entity': {'type': 'job', 'id': 'job-1'},
            'event': {'kind': 'started', 'at': '2025-10-19T12:00:00Z'}
        }
        
        success = await integration.send_event(event)
        assert success
        
        # Check file was created
        json_files = list(tmp_path.glob('*.jsonl'))
        assert len(json_files) > 0
        
        await integration.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

