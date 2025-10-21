"""
Configuration Management for Sidecar
"""

import yaml
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TCPConfig:
    """TCP listener configuration"""
    host: str = "127.0.0.1"
    port: int = 17000
    max_connections: int = 100
    read_timeout: int = 30


@dataclass
class BufferConfig:
    """Buffer configuration"""
    max_queue_size: int = 10000
    per_source_buffer: int = 1000
    flush_interval: int = 5  # seconds
    flush_batch_size: int = 100


@dataclass
class BackendConfig:
    """Backend configuration"""
    type: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingRule:
    """Routing rule for a source"""
    backend: str
    enabled: bool = True
    priority: int = 1
    filter: Optional[Dict[str, Any]] = None


@dataclass
class SidecarConfig:
    """Main sidecar configuration"""
    tcp: TCPConfig
    buffers: BufferConfig
    backends: Dict[str, BackendConfig]
    routing: Dict[str, List[RoutingRule]]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SidecarConfig':
        """Create config from dictionary"""
        tcp = TCPConfig(**data.get('tcp', {}))
        buffers = BufferConfig(**data.get('buffers', {}))
        
        # Parse backends
        backends = {}
        for name, backend_data in data.get('backends', {}).items():
            backends[name] = BackendConfig(
                type=backend_data['type'],
                enabled=backend_data.get('enabled', True),
                config=backend_data.get('config', {})
            )
        
        # Parse routing rules
        routing = {}
        for source, rules_data in data.get('routing', {}).items():
            rules = []
            for rule_data in rules_data:
                rules.append(RoutingRule(
                    backend=rule_data['backend'],
                    enabled=rule_data.get('enabled', True),
                    priority=rule_data.get('priority', 1),
                    filter=rule_data.get('filter')
                ))
            routing[source] = rules
        
        return cls(tcp=tcp, buffers=buffers, backends=backends, routing=routing)
    
    @classmethod
    def from_file(cls, config_path: str) -> 'SidecarConfig':
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def get_routing_rules(self, source: str) -> List[RoutingRule]:
        """Get routing rules for a source"""
        # First try exact match
        if source in self.routing:
            return self.routing[source]
        
        # Fall back to default rules
        if 'default' in self.routing:
            return self.routing['default']
        
        return []
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Validate backend references in routing
        for source, rules in self.routing.items():
            for rule in rules:
                if rule.backend not in self.backends:
                    errors.append(f"Unknown backend '{rule.backend}' in routing for '{source}'")
        
        # Validate backend configs
        for name, backend in self.backends.items():
            if backend.type == 'timescaledb':
                if 'connection_string' not in backend.config:
                    errors.append(f"Backend '{name}': missing 'connection_string'")
            
            elif backend.type == 'filesystem':
                if 'base_path' not in backend.config:
                    errors.append(f"Backend '{name}': missing 'base_path'")
            
            elif backend.type == 's3':
                if 'bucket' not in backend.config:
                    errors.append(f"Backend '{name}': missing 'bucket'")
        
        return errors


# Example configuration
EXAMPLE_CONFIG = """
tcp:
  host: "127.0.0.1"
  port: 17000
  max_connections: 100

buffers:
  max_queue_size: 10000
  per_source_buffer: 1000
  flush_interval: 5
  flush_batch_size: 100

backends:
  timescaledb:
    type: timescaledb
    enabled: true
    config:
      connection_string: "postgresql://user:pass@localhost:5432/monitoring"
      table: monitoring_events
  
  filesystem:
    type: filesystem
    enabled: true
    config:
      base_path: /tmp/monitoring-logs
  
  s3:
    type: s3
    enabled: false
    config:
      bucket: monitoring-events
      region: us-east-1

routing:
  queue-service:
    - backend: timescaledb
      enabled: true
      priority: 1
      filter:
        types: [metric, event]
    
    - backend: filesystem
      enabled: true
      priority: 2
      filter:
        types: [event]
  
  config-service:
    - backend: s3
      enabled: true
      priority: 1
  
  default:
    - backend: filesystem
      enabled: true
      priority: 1
"""


if __name__ == '__main__':
    # Test configuration loading
    import tempfile
    
    # Create temp config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(EXAMPLE_CONFIG)
        config_path = f.name
    
    try:
        # Load config
        config = SidecarConfig.from_file(config_path)
        print("✓ Config loaded")
        print(f"  TCP: {config.tcp.host}:{config.tcp.port}")
        print(f"  Backends: {list(config.backends.keys())}")
        print(f"  Routing sources: {list(config.routing.keys())}")
        
        # Validate
        errors = config.validate()
        if errors:
            print("✗ Validation errors:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("✓ Config valid")
        
        # Test routing lookup
        rules = config.get_routing_rules('queue-service')
        print(f"✓ Queue service routes to: {[r.backend for r in rules]}")
        
    finally:
        os.unlink(config_path)

