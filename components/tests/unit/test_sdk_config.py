"""Tests for SDK configuration system."""

import pytest
import tempfile
from pathlib import Path
import json
import yaml

# Add SDK to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "monitoring/sdk/python"))

from monitoring_sdk.config import (
    MonitoringConfig,
    SDKMode,
    BackendType,
    BackendConfig,
    AppConfig,
    SidecarConfig,
    ConfigLoader,
    configure,
    get_config,
    reset_config
)


class TestMonitoringConfig:
    """Test MonitoringConfig class."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = MonitoringConfig()
        
        assert config.mode == SDKMode.SIDECAR
        assert config.sidecar.url == "http://localhost:17000"
        assert config.app.name == "unknown-app"
    
    def test_get_active_backends(self):
        """Test getting active backends sorted by priority."""
        config = MonitoringConfig(
            mode=SDKMode.DIRECT,
            direct_backends=[
                BackendConfig(type=BackendType.S3, priority=3),
                BackendConfig(type=BackendType.FILESYSTEM, priority=1),
                BackendConfig(type=BackendType.ELK, priority=2, enabled=False),
            ]
        )
        
        active = config.get_active_backends()
        assert len(active) == 2
        assert active[0].type == BackendType.FILESYSTEM
        assert active[1].type == BackendType.S3


class TestConfigLoader:
    """Test ConfigLoader functionality."""
    
    def test_load_from_dict(self):
        """Test loading configuration from dictionary."""
        data = {
            'sdk': {
                'mode': 'direct',
                'sidecar': {
                    'url': 'http://custom:17000'
                },
                'direct_backends': [
                    {
                        'type': 'filesystem',
                        'enabled': True,
                        'priority': 1,
                        'config': {
                            'path': '/data/events'
                        }
                    }
                ],
                'app': {
                    'name': 'test-app',
                    'version': '1.0.0',
                    'site_id': 'fab1'
                }
            }
        }
        
        config = ConfigLoader.from_dict(data)
        
        assert config.mode == SDKMode.DIRECT
        assert config.sidecar.url == 'http://custom:17000'
        assert len(config.direct_backends) == 1
        assert config.direct_backends[0].type == BackendType.FILESYSTEM
        assert config.app.name == 'test-app'
    
    def test_load_from_yaml(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
sdk:
  mode: sidecar
  sidecar:
    url: http://sidecar:17000
    timeout: 10.0
  app:
    name: yaml-app
    version: 2.0.0
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_file = f.name
        
        try:
            config = ConfigLoader.from_file(yaml_file)
            
            assert config.mode == SDKMode.SIDECAR
            assert config.sidecar.url == 'http://sidecar:17000'
            assert config.sidecar.timeout == 10.0
            assert config.app.name == 'yaml-app'
        finally:
            Path(yaml_file).unlink()
    
    def test_load_from_json(self):
        """Test loading configuration from JSON file."""
        json_data = {
            'sdk': {
                'mode': 'direct',
                'app': {
                    'name': 'json-app'
                },
                'direct_backends': [
                    {
                        'type': 's3',
                        'config': {
                            'bucket': 'my-bucket'
                        }
                    }
                ]
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(json_data, f)
            json_file = f.name
        
        try:
            config = ConfigLoader.from_file(json_file)
            
            assert config.mode == SDKMode.DIRECT
            assert config.app.name == 'json-app'
            assert len(config.direct_backends) == 1
            assert config.direct_backends[0].type == BackendType.S3
        finally:
            Path(json_file).unlink()
    
    def test_load_from_env(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv('MONITORING_MODE', 'direct')
        monkeypatch.setenv('MONITORING_SIDECAR_URL', 'http://env:17000')
        monkeypatch.setenv('MONITORING_SIDECAR_TIMEOUT', '15.0')
        monkeypatch.setenv('MONITORING_APP_NAME', 'env-app')
        monkeypatch.setenv('MONITORING_APP_VERSION', '3.0.0')
        monkeypatch.setenv('MONITORING_APP_SITE_ID', 'fab2')
        
        config = ConfigLoader.from_env()
        
        assert config.mode == SDKMode.DIRECT
        assert config.sidecar.url == 'http://env:17000'
        assert config.sidecar.timeout == 15.0
        assert config.app.name == 'env-app'
        assert config.app.version == '3.0.0'
        assert config.app.site_id == 'fab2'


class TestGlobalConfig:
    """Test global configuration management."""
    
    def setup_method(self):
        """Reset config before each test."""
        reset_config()
    
    def test_configure_with_dict(self):
        """Test configuring globally with dictionary."""
        config_dict = {
            'sdk': {
                'mode': 'sidecar',
                'app': {
                    'name': 'global-app'
                }
            }
        }
        
        configure(config_dict)
        config = get_config()
        
        assert config.app.name == 'global-app'
    
    def test_configure_with_kwargs(self):
        """Test configuring with keyword arguments."""
        configure(
            mode='direct',
            app_name='kwargs-app',
            app_version='1.2.3'
        )
        
        config = get_config()
        
        assert config.mode == SDKMode.DIRECT
        assert config.app.name == 'kwargs-app'
        assert config.app.version == '1.2.3'
    
    def test_auto_configure_from_env(self, monkeypatch):
        """Test auto-configuration from environment."""
        monkeypatch.setenv('MONITORING_APP_NAME', 'auto-app')
        
        # Don't call configure(), just get_config()
        config = get_config()
        
        assert config.app.name == 'auto-app'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

