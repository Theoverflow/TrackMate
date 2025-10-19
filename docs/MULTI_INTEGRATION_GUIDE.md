# Multi-Integration System - Complete Guide

## 🎯 Overview

The Wafer Monitor system now supports **simultaneous integration with multiple backends** using a **dependency injection pattern**. This allows you to send monitoring data to any combination of systems in real-time.

## ✨ Key Features

- **6 Built-in Integrations**: Local API, Zabbix, ELK, CSV, JSON, Webhook
- **Dependency Injection**: Clean, extensible architecture
- **Simultaneous Delivery**: Send to all integrations concurrently
- **Resilience**: Spooling for failed deliveries
- **Health Monitoring**: Individual integration health checks
- **Easy Configuration**: JSON-based configuration
- **Custom Integrations**: Extend with your own backends

## 🏗️ Architecture

### Dependency Injection Container

```
┌──────────────────────────────────────────────────────────┐
│           IntegrationContainer (DI Container)             │
│                                                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐         │
│  │ Local API  │  │  Zabbix    │  │    ELK     │         │
│  │Integration │  │Integration │  │Integration │         │
│  └────────────┘  └────────────┘  └────────────┘         │
│                                                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐         │
│  │    CSV     │  │    JSON    │  │  Webhook   │         │
│  │ Integration│  │Integration │  │Integration │         │
│  └────────────┘  └────────────┘  └────────────┘         │
└──────────────────────────────────────────────────────────┘
```

### Integration Interface

All integrations implement `BaseIntegration`:

```python
class BaseIntegration(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        """Setup connection/resources"""
        
    @abstractmethod
    async def send_event(self, event: Dict) -> bool:
        """Send single event"""
        
    @abstractmethod
    async def send_batch(self, events: List[Dict]) -> Dict[str, int]:
        """Send batch of events"""
        
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check integration health"""
        
    @abstractmethod
    async def close(self) -> None:
        """Cleanup resources"""
```

## 📦 Available Integrations

### 1. Local API (TimescaleDB)

**Purpose**: Primary data storage and query engine

**Use Case**: 
- Real-time monitoring data
- Short-term hot storage (72 hours)
- Query interface for dashboards

**Configuration**:
```json
{
  "type": "local_api",
  "name": "primary-db",
  "enabled": true,
  "config": {
    "base_url": "http://localhost:18000",
    "timeout": 5.0
  }
}
```

### 2. Zabbix Integration

**Purpose**: Infrastructure and application monitoring

**Use Case**:
- Real-time alerting
- Performance monitoring
- Capacity planning

**Configuration**:
```json
{
  "type": "zabbix",
  "name": "zabbix-prod",
  "enabled": true,
  "config": {
    "zabbix_server": "http://zabbix:10051",
    "host": "wafer-monitor"
  }
}
```

**Zabbix Items Created**:
- `wafer.job.started` - Job start count
- `wafer.job.finished` - Job completion with duration
- `wafer.subjob.started` - Subjob start count
- `wafer.subjob.finished` - Subjob completion

### 3. ELK Integration (Elasticsearch)

**Purpose**: Log aggregation and analytics

**Use Case**:
- Long-term trend analysis
- Complex queries with Kibana
- Data visualization
- Anomaly detection

**Configuration**:
```json
{
  "type": "elk",
  "name": "elasticsearch",
  "enabled": true,
  "config": {
    "elasticsearch_url": "http://elasticsearch:9200",
    "index_prefix": "wafer-monitor",
    "username": "elastic",
    "password": "changeme"
  }
}
```

**Index Pattern**: `wafer-monitor-YYYY.MM.DD`

**Document Structure**:
```json
{
  "timestamp": "2025-10-19T12:00:00Z",
  "site_id": "fab1",
  "app_name": "processor",
  "entity_type": "job",
  "event_kind": "finished",
  "status": "succeeded",
  "duration_s": 120.5,
  "cpu_user_s": 45.2,
  "mem_max_mb": 2048.0
}
```

### 4. CSV Export Integration

**Purpose**: Local file backup in CSV format

**Use Case**:
- Compliance and audit requirements
- Offline analysis with Excel/R/Python
- Backup and disaster recovery
- Data portability

**Configuration**:
```json
{
  "type": "csv",
  "name": "csv-backup",
  "enabled": true,
  "config": {
    "output_dir": "/var/log/wafer-monitor",
    "rotation": "daily",
    "include_headers": true,
    "delimiter": ","
  }
}
```

**File Format**: `wafer_events_YYYYMMDD.csv`

### 5. JSON Export Integration

**Purpose**: Structured data export in JSONL format

**Use Case**:
- Machine learning pipelines
- Data science analysis
- Custom processing scripts
- Integration testing

**Configuration**:
```json
{
  "type": "json",
  "name": "json-export",
  "enabled": true,
  "config": {
    "output_dir": "/var/log/wafer-monitor",
    "rotation": "daily",
    "pretty_print": false,
    "compression": true
  }
}
```

**File Format**: `wafer_events_YYYYMMDD.jsonl(.gz)`

### 6. Webhook Integration

**Purpose**: Integration with any HTTP API

**Use Case**:
- Custom internal systems
- Third-party SaaS platforms
- Notification services (PagerDuty, Opsgenie)
- Workflow automation

**Configuration**:
```json
{
  "type": "webhook",
  "name": "custom-system",
  "enabled": true,
  "config": {
    "webhook_url": "https://api.company.com/events",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer token123",
      "X-Custom-Header": "value"
    },
    "timeout": 5.0,
    "verify_ssl": true
  }
}
```

## 🚀 Quick Start

### Step 1: Configure Integrations

Create `integrations.json`:

```json
[
  {
    "type": "local_api",
    "name": "primary",
    "enabled": true,
    "config": {"base_url": "http://localhost:18000"}
  },
  {
    "type": "csv",
    "name": "backup",
    "enabled": true,
    "config": {"output_dir": "/backup", "rotation": "daily"}
  }
]
```

### Step 2: Set Environment Variable

```bash
export INTEGRATIONS_CONFIG=$(cat integrations.json)
```

### Step 3: Start Multi-Integration Sidecar

```bash
python apps/sidecar_agent/main_multi_integration.py
```

### Step 4: Verify Integrations

```bash
curl http://localhost:8000/v1/integrations
```

Response:
```json
{
  "total": 2,
  "enabled": 2,
  "integrations": ["primary", "backup"],
  "enabled_integrations": ["primary", "backup"]
}
```

## 📊 Real-World Scenarios

### Scenario 1: Production Manufacturing

**Requirements**:
- Real-time monitoring in Zabbix
- Data storage in TimescaleDB
- Compliance backup to CSV
- Analytics in Elasticsearch

**Configuration**:
```json
[
  {
    "type": "local_api",
    "name": "timescaledb",
    "enabled": true,
    "config": {"base_url": "http://local-api:18000"}
  },
  {
    "type": "zabbix",
    "name": "monitoring",
    "enabled": true,
    "config": {
      "zabbix_server": "http://zabbix:10051",
      "host": "fab1-wafer-monitor"
    }
  },
  {
    "type": "csv",
    "name": "compliance",
    "enabled": true,
    "config": {
      "output_dir": "/compliance/logs",
      "rotation": "daily"
    }
  },
  {
    "type": "elk",
    "name": "analytics",
    "enabled": true,
    "config": {
      "elasticsearch_url": "http://elasticsearch:9200",
      "index_prefix": "fab1-wafer"
    }
  }
]
```

### Scenario 2: Development & Testing

**Requirements**:
- Local TimescaleDB for testing
- JSON export for debugging
- Optional CSV for analysis

**Configuration**:
```json
[
  {
    "type": "local_api",
    "name": "dev-db",
    "enabled": true,
    "config": {"base_url": "http://localhost:18000"}
  },
  {
    "type": "json",
    "name": "debug",
    "enabled": true,
    "config": {
      "output_dir": "./debug-logs",
      "pretty_print": true,
      "rotation": "none"
    }
  }
]
```

### Scenario 3: Cloud-Native Deployment

**Requirements**:
- Managed Elasticsearch (AWS/GCP/Azure)
- CloudWatch/Stackdriver via webhook
- S3 backup

**Configuration**:
```json
[
  {
    "type": "elk",
    "name": "managed-elasticsearch",
    "enabled": true,
    "config": {
      "elasticsearch_url": "https://vpc-domain.region.es.amazonaws.com",
      "api_key": "base64-encoded-key"
    }
  },
  {
    "type": "webhook",
    "name": "cloudwatch",
    "enabled": true,
    "config": {
      "webhook_url": "https://logs.region.amazonaws.com/v1/logs",
      "headers": {"X-Amz-Token": "${AWS_TOKEN}"}
    }
  }
]
```

## 🔧 Advanced Usage

### Custom Integration

Create your own integration:

```python
from shared_utils.integrations.base import BaseIntegration, IntegrationConfig

class RedisIntegration(BaseIntegration):
    """Send events to Redis streams."""
    
    async def initialize(self) -> None:
        import redis.asyncio as redis
        self.redis = await redis.from_url(
            self.get_config('redis_url')
        )
    
    async def send_event(self, event: Dict) -> bool:
        await self.redis.xadd(
            'wafer:events',
            {'data': json.dumps(event)}
        )
        return True
    
    # Implement other methods...
```

Register it:

```python
from shared_utils.integrations import IntegrationContainer

IntegrationContainer.INTEGRATION_REGISTRY['redis'] = RedisIntegration
```

### Conditional Forwarding

Forward different event types to different backends:

```python
class FilteredIntegration(BaseIntegration):
    async def send_event(self, event: Dict) -> bool:
        # Only send 'failed' events
        if event['event']['status'] != 'failed':
            return True  # Skip but report success
        
        # Forward to actual backend
        return await self._actual_send(event)
```

### Transformation Pipeline

Transform events before sending:

```python
class TransformingIntegration(BaseIntegration):
    async def send_event(self, event: Dict) -> bool:
        # Transform event format
        transformed = {
            'timestamp': event['event']['at'],
            'severity': self._map_severity(event),
            'message': self._format_message(event)
        }
        
        return await self._send_transformed(transformed)
```

## 📈 Monitoring

### Health Checks

```bash
curl http://localhost:8000/v1/healthz
```

Response shows individual integration health:
```json
{
  "status": "ok",
  "integrations": {
    "primary": {
      "status": "healthy",
      "backend": "local_api"
    },
    "zabbix": {
      "status": "healthy",
      "backend": "zabbix"
    },
    "csv": {
      "status": "healthy",
      "backend": "csv_export",
      "writable": true
    }
  }
}
```

### Metrics

```bash
curl http://localhost:8000/metrics | grep integration
```

Integration-specific metrics:
- `events_processed_total{integration="zabbix",status="success"}`
- `events_processed_total{integration="elk",status="failed"}`

## 🎓 Best Practices

### 1. Always Enable Local API

Keep TimescaleDB as primary storage for queries and dashboards.

### 2. Use CSV/JSON for Backup

Local file exports provide resilience and compliance.

### 3. Monitor Integration Health

Set up alerts on integration failures:

```bash
curl http://localhost:8000/v1/healthz | jq '.integrations[] | select(.status != "healthy")'
```

### 4. Test Integrations Separately

Enable one at a time during initial setup:

```json
[
  {"type": "local_api", "name": "test", "enabled": true, "config": {...}},
  {"type": "zabbix", "name": "test", "enabled": false, "config": {...}}
]
```

### 5. Use Appropriate Rotation

- **Hourly**: High-volume environments
- **Daily**: Normal operations
- **None**: Testing/development

### 6. Secure Credentials

Use environment variables for sensitive data:

```json
{
  "config": {
    "api_key": "${ELASTICSEARCH_API_KEY}",
    "password": "${DATABASE_PASSWORD}"
  }
}
```

## 🐛 Troubleshooting

### Integration Not Receiving Events

1. **Check if enabled**:
   ```bash
   curl http://localhost:8000/v1/integrations
   ```

2. **Check health**:
   ```bash
   curl http://localhost:8000/v1/healthz
   ```

3. **Check logs**:
   ```bash
   docker logs sidecar-agent | grep integration_name
   ```

### Partial Delivery

Events are spooled only if **all** integrations fail. If any succeeds, the event is considered delivered.

### Performance Issues

- Reduce number of integrations
- Increase timeouts
- Use batch operations
- Check network latency

### File Permission Errors (CSV/JSON)

```bash
# Ensure directory is writable
chmod 755 /var/log/wafer-monitor
chown app-user:app-group /var/log/wafer-monitor
```

## 📚 References

- [Complete Integration Documentation](INTEGRATIONS.md)
- [API Reference](API.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Example Configurations](../examples/integrations/)

## 🎉 Summary

The multi-integration system provides:

✅ **Flexibility** - Send to any combination of backends  
✅ **Resilience** - Automatic spooling and retry  
✅ **Extensibility** - Easy to add custom integrations  
✅ **Observability** - Health checks and metrics  
✅ **Performance** - Concurrent async delivery  
✅ **Simplicity** - JSON configuration  

Your monitoring data can now reach any system, anywhere! 🚀

