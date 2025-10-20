"""
Universal configuration system for Monitoring SDK.

Supports multiple configuration sources:
- YAML/JSON files
- Environment variables
- Programmatic configuration

Example YAML:
    sdk:
      mode: sidecar  # or "direct"
      sidecar:
        url: http://localhost:17000
        timeout: 5.0
        retries: 3
      direct_backends:
        - type: filesystem
          enabled: true
          priority: 1
          config:
            path: /data/monitoring
            format: jsonl
        - type: s3
          enabled: true
          priority: 2
          config:
            bucket: monitoring-events
            region: us-east-1
      app:
        name: wafer-processing
        version: 1.0.0
        site_id: fab1
"""

import os
import yaml
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


class SDKMode(str, Enum):
    """SDK routing mode."""
    SIDECAR = "sidecar"
    DIRECT = "direct"


class BackendType(str, Enum):
    """Backend types."""
    SIDECAR = "sidecar"
    FILESYSTEM = "filesystem"
    S3 = "s3"
    ELK = "elk"
    ZABBIX = "zabbix"
    CLOUDWATCH = "cloudwatch"
    WEBHOOK = "webhook"
    KAFKA = "kafka"
    SQS = "sqs"


@dataclass
class SidecarConfig:
    """Configuration for sidecar mode."""
    url: str = "http://localhost:17000"
    timeout: float = 5.0
    retries: int = 3
    enable_spooling: bool = True
    spool_dir: str = "/tmp/sdk-spool"


@dataclass
class BackendConfig:
    """Configuration for a direct backend."""
    type: BackendType
    enabled: bool = True
    priority: int = 1
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfig:
    """Application metadata."""
    name: str
    version: str = "1.0.0"
    site_id: str = "default"
    instance_id: Optional[str] = None
    
    def __post_init__(self):
        if self.instance_id is None:
            self.instance_id = os.getenv('HOSTNAME', 'unknown')


@dataclass
class MonitoringConfig:
    """Complete monitoring configuration."""
    mode: SDKMode = SDKMode.SIDECAR
    sidecar: SidecarConfig = field(default_factory=SidecarConfig)
    direct_backends: List[BackendConfig] = field(default_factory=list)
    app: AppConfig = None
    
    def __post_init__(self):
        if self.app is None:
            self.app = AppConfig(name="unknown-app")
    
    def get_active_backends(self) -> List[BackendConfig]:
        """Get list of enabled backends sorted by priority."""
        backends = [b for b in self.direct_backends if b.enabled]
        return sorted(backends, key=lambda x: x.priority)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ConfigLoader:
    """Load configuration from various sources."""
    
    @staticmethod
    def from_file(path: Union[str, Path]) -> MonitoringConfig:
        """
        Load configuration from YAML or JSON file.
        
        Args:
            path: Path to configuration file
            
        Returns:
            MonitoringConfig instance
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif path.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")
        
        return ConfigLoader.from_dict(data)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> MonitoringConfig:
        """
        Load configuration from dictionary.
        
        Args:
            data: Configuration dictionary
            
        Returns:
            MonitoringConfig instance
        """
        sdk_config = data.get('sdk', {})
        
        # Parse mode
        mode = SDKMode(sdk_config.get('mode', 'sidecar'))
        
        # Parse sidecar config
        sidecar_data = sdk_config.get('sidecar', {})
        sidecar = SidecarConfig(**sidecar_data)
        
        # Parse direct backends
        backends = []
        for backend_data in sdk_config.get('direct_backends', []):
            backend_type = BackendType(backend_data['type'])
            backend = BackendConfig(
                type=backend_type,
                enabled=backend_data.get('enabled', True),
                priority=backend_data.get('priority', 1),
                config=backend_data.get('config', {})
            )
            backends.append(backend)
        
        # Parse app config
        app_data = sdk_config.get('app', {})
        if not app_data.get('name'):
            app_data['name'] = 'unknown-app'
        app = AppConfig(**app_data)
        
        return MonitoringConfig(
            mode=mode,
            sidecar=sidecar,
            direct_backends=backends,
            app=app
        )
    
    @staticmethod
    def from_env() -> MonitoringConfig:
        """
        Load configuration from environment variables.
        
        Environment variables:
            MONITORING_MODE: sidecar or direct
            MONITORING_SIDECAR_URL: Sidecar URL
            MONITORING_SIDECAR_TIMEOUT: Timeout in seconds
            MONITORING_SIDECAR_RETRIES: Retry count
            MONITORING_APP_NAME: Application name
            MONITORING_APP_VERSION: Application version
            MONITORING_APP_SITE_ID: Site identifier
            
        Returns:
            MonitoringConfig instance
        """
        mode = SDKMode(os.getenv('MONITORING_MODE', 'sidecar'))
        
        sidecar = SidecarConfig(
            url=os.getenv('MONITORING_SIDECAR_URL', 'http://localhost:17000'),
            timeout=float(os.getenv('MONITORING_SIDECAR_TIMEOUT', '5.0')),
            retries=int(os.getenv('MONITORING_SIDECAR_RETRIES', '3')),
            enable_spooling=os.getenv('MONITORING_SIDECAR_SPOOLING', 'true').lower() == 'true',
            spool_dir=os.getenv('MONITORING_SIDECAR_SPOOL_DIR', '/tmp/sdk-spool')
        )
        
        app = AppConfig(
            name=os.getenv('MONITORING_APP_NAME', 'unknown-app'),
            version=os.getenv('MONITORING_APP_VERSION', '1.0.0'),
            site_id=os.getenv('MONITORING_APP_SITE_ID', 'default'),
            instance_id=os.getenv('MONITORING_APP_INSTANCE_ID') or os.getenv('HOSTNAME')
        )
        
        return MonitoringConfig(
            mode=mode,
            sidecar=sidecar,
            app=app
        )
    
    @staticmethod
    def load(
        config_file: Optional[Union[str, Path]] = None,
        env_override: bool = True
    ) -> MonitoringConfig:
        """
        Load configuration with precedence:
        1. Environment variables (if env_override=True)
        2. Configuration file (if provided)
        3. Default values
        
        Args:
            config_file: Optional path to configuration file
            env_override: Whether environment variables override file config
            
        Returns:
            MonitoringConfig instance
        """
        # Start with defaults
        config = MonitoringConfig()
        
        # Load from file if provided
        if config_file:
            config = ConfigLoader.from_file(config_file)
        
        # Override with environment variables
        if env_override:
            if os.getenv('MONITORING_MODE'):
                config.mode = SDKMode(os.getenv('MONITORING_MODE'))
            
            if os.getenv('MONITORING_SIDECAR_URL'):
                config.sidecar.url = os.getenv('MONITORING_SIDECAR_URL')
            
            if os.getenv('MONITORING_SIDECAR_TIMEOUT'):
                config.sidecar.timeout = float(os.getenv('MONITORING_SIDECAR_TIMEOUT'))
            
            if os.getenv('MONITORING_APP_NAME'):
                config.app.name = os.getenv('MONITORING_APP_NAME')
            
            if os.getenv('MONITORING_APP_SITE_ID'):
                config.app.site_id = os.getenv('MONITORING_APP_SITE_ID')
        
        return config


# Global configuration instance
_global_config: Optional[MonitoringConfig] = None


def configure(
    config: Optional[Union[MonitoringConfig, Dict, str, Path]] = None,
    **kwargs
) -> MonitoringConfig:
    """
    Configure the monitoring SDK globally.
    
    Args:
        config: MonitoringConfig instance, dict, or path to config file
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured MonitoringConfig instance
        
    Examples:
        # From file
        configure("/path/to/config.yaml")
        
        # From dict
        configure({"sdk": {"mode": "sidecar", ...}})
        
        # From kwargs
        configure(mode="direct", app_name="my-app")
        
        # From MonitoringConfig
        config = MonitoringConfig(...)
        configure(config)
    """
    global _global_config
    
    if config is None:
        # Load from environment or defaults
        _global_config = ConfigLoader.load()
    elif isinstance(config, MonitoringConfig):
        _global_config = config
    elif isinstance(config, dict):
        _global_config = ConfigLoader.from_dict(config)
    elif isinstance(config, (str, Path)):
        _global_config = ConfigLoader.load(config)
    else:
        raise ValueError(f"Invalid config type: {type(config)}")
    
    # Apply kwargs overrides
    if 'mode' in kwargs:
        _global_config.mode = SDKMode(kwargs['mode'])
    if 'sidecar_url' in kwargs:
        _global_config.sidecar.url = kwargs['sidecar_url']
    if 'app_name' in kwargs:
        _global_config.app.name = kwargs['app_name']
    if 'app_version' in kwargs:
        _global_config.app.version = kwargs['app_version']
    if 'site_id' in kwargs:
        _global_config.app.site_id = kwargs['site_id']
    
    return _global_config


def get_config() -> MonitoringConfig:
    """
    Get the global configuration.
    
    Returns:
        MonitoringConfig instance
        
    Raises:
        RuntimeError: If SDK is not configured
    """
    global _global_config
    
    if _global_config is None:
        # Auto-configure from environment
        _global_config = ConfigLoader.from_env()
    
    return _global_config


def reset_config():
    """Reset global configuration (mainly for testing)."""
    global _global_config
    _global_config = None

