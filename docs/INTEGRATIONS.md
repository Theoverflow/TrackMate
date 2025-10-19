

# Multi-Integration System Guide

## Overview

The Wafer Monitor system supports simultaneous integration with multiple backends using a **dependency injection** pattern. You can send monitoring events to any combination of:

- **Local API** (TimescaleDB) - Primary storage
- **Zabbix** - Infrastructure monitoring
- **ELK Stack** (Elasticsearch) - Log aggregation and analytics
- **CSV Export** - Local file export
- **JSON Export** - JSONL format export
- **Webhook** - Custom HTTP endpoints

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Business Application                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Sidecar Agent                            │
│                (Dependency Injection Container)              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          Integration Manager (Container)              │  │
│  └───────────────────────────────────────────────────────┘  │
│         │         │         │         │         │            │
│         ▼         ▼         ▼         ▼         ▼            │
│   ┌────────┐ ┌────────┐ ┌──────┐ ┌─────┐ ┌────────┐        │
│   │Local   │ │Zabbix  │ │ ELK  │ │ CSV │ │ JSON   │        │
│   │  API   │ │        │ │      │ │     │ │        │        │
│   └────────┘ └────────┘ └──────┘ └─────┘ └────────┘        │
└─────────────────────────────────────────────────────────────┘
         │         │         │         │         │
         ▼         ▼         ▼         ▼         ▼
    TimescaleDB  Zabbix  Elasticsearch  File   File
```

## Configuration

### Option 1: Environment Variable (Recommended)

Set the `INTEGRATIONS_CONFIG` environment variable with JSON configuration:

```bash
export INTEGRATIONS_CONFIG='[
  {
    "type": "local_api",
    "name": "primary-db",
    "enabled": true,
    "config": {
      "base_url": "http://localhost:18000",
      "timeout": 5.0
    }
  },
  {
    "type": "zabbix",
    "name": "zabbix-prod",
    "enabled": true,
    "config": {
      "zabbix_server": "http://zabbix:10051",
      "host": "wafer-monitor-fab1"
    }
  },
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
  },
  {
    "type": "csv",
    "name": "csv-backup",
    "enabled": true,
    "config": {
      "output_dir": "/var/log/wafer-monitor",
      "rotation": "daily",
      "include_headers": true
    }
  },
  {
    "type": "json",
    "name": "json-export",
    "enabled": false,
    "config": {
      "output_dir": "/var/log/wafer-monitor/json",
      "rotation": "daily",
      "compression": true
    }
  },
  {
    "type": "webhook",
    "name": "custom-system",
    "enabled": true,
    "config": {
      "webhook_url": "https://your-system.com/api/events",
      "method": "POST",
      "headers": {
        "Authorization": "Bearer your-token"
      }
    }
  }
]'
```

### Option 2: Configuration File

Create a `integrations.json` file:

```json
[
  {
    "type": "local_api",
    "name": "primary-db",
    "enabled": true,
    "config": {
      "base_url": "http://localhost:18000"
    }
  },
  {
    "type": "zabbix",
    "name": "zabbix-prod",
    "enabled": true,
    "config": {
      "zabbix_server": "http://zabbix:10051",
      "host": "wafer-monitor"
    }
  }
]
```

Then load it:

```bash
export INTEGRATIONS_CONFIG=$(cat integrations.json)
```

## Integration Types

### 1. Local API Integration

**Type**: `local_api`

Sends events to the Local API (TimescaleDB backend).

**Configuration:**
```json
{
  "type": "local_api",
  "name": "primary",
  "enabled": true,
  "config": {
    "base_url": "http://localhost:18000",
    "timeout": 5.0
  }
}
```

**Parameters:**
- `base_url` (required) - Local API URL
- `timeout` (optional, default: 5.0) - Request timeout in seconds

### 2. Zabbix Integration

**Type**: `zabbix`

Sends events to Zabbix monitoring system as trapper items.

**Configuration:**
```json
{
  "type": "zabbix",
  "name": "zabbix-prod",
  "enabled": true,
  "config": {
    "zabbix_server": "http://zabbix:10051",
    "host": "wafer-monitor",
    "auth_token": "optional-token"
  }
}
```

**Parameters:**
- `zabbix_server` (required) - Zabbix server URL
- `host` (required) - Zabbix host name
- `auth_token` (optional) - Authentication token

**Zabbix Items Created:**
- `wafer.job.started` - Job start events
- `wafer.job.finished` - Job completion events
- `wafer.subjob.started` - Subjob start events
- `wafer.subjob.finished` - Subjob completion events

### 3. ELK Integration

**Type**: `elk`

Sends events directly to Elasticsearch for Kibana visualization.

**Configuration:**
```json
{
  "type": "elk",
  "name": "elasticsearch",
  "enabled": true,
  "config": {
    "elasticsearch_url": "http://elasticsearch:9200",
    "index_prefix": "wafer-monitor",
    "username": "elastic",
    "password": "changeme",
    "api_key": "base64-encoded-api-key"
  }
}
```

**Parameters:**
- `elasticsearch_url` (required) - Elasticsearch URL
- `index_prefix` (optional, default: wafer-monitor) - Index name prefix
- `username` (optional) - Basic auth username
- `password` (optional) - Basic auth password
- `api_key` (optional) - API key (alternative to username/password)

**Index Pattern:** `{index_prefix}-YYYY.MM.DD`

**Example:** `wafer-monitor-2025.10.19`

### 4. CSV Export Integration

**Type**: `csv`

Exports events to CSV files with automatic rotation.

**Configuration:**
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

**Parameters:**
- `output_dir` (required) - Output directory path
- `rotation` (optional, default: daily) - Rotation strategy (hourly, daily, none)
- `include_headers` (optional, default: true) - Include CSV headers
- `delimiter` (optional, default: ,) - CSV delimiter

**File Pattern:** `wafer_events_YYYYMMDD.csv`

### 5. JSON Export Integration

**Type**: `json`

Exports events to JSONL (JSON Lines) format with optional compression.

**Configuration:**
```json
{
  "type": "json",
  "name": "json-export",
  "enabled": true,
  "config": {
    "output_dir": "/var/log/wafer-monitor/json",
    "rotation": "daily",
    "pretty_print": false,
    "compression": true
  }
}
```

**Parameters:**
- `output_dir` (required) - Output directory path
- `rotation` (optional, default: daily) - Rotation strategy (hourly, daily, none)
- `pretty_print` (optional, default: false) - Format JSON with indentation
- `compression` (optional, default: false) - Enable gzip compression

**File Pattern:** `wafer_events_YYYYMMDD.jsonl` or `.jsonl.gz`

### 6. Webhook Integration

**Type**: `webhook`

Sends events to any HTTP endpoint with configurable format.

**Configuration:**
```json
{
  "type": "webhook",
  "name": "custom-system",
  "enabled": true,
  "config": {
    "webhook_url": "https://your-system.com/api/events",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer your-token",
      "X-Custom-Header": "value"
    },
    "timeout": 5.0,
    "verify_ssl": true
  }
}
```

**Parameters:**
- `webhook_url` (required) - Target webhook URL
- `method` (optional, default: POST) - HTTP method (POST, PUT, PATCH)
- `headers` (optional) - Custom headers dictionary
- `timeout` (optional, default: 5.0) - Request timeout
- `verify_ssl` (optional, default: true) - Verify SSL certificates

## Usage Examples

### Example 1: Production Setup

Send to Local API, Elasticsearch, and CSV backup:

```bash
export INTEGRATIONS_CONFIG='[
  {
    "type": "local_api",
    "name": "primary",
    "enabled": true,
    "config": {"base_url": "http://local-api:18000"}
  },
  {
    "type": "elk",
    "name": "elasticsearch",
    "enabled": true,
    "config": {
      "elasticsearch_url": "http://elasticsearch:9200",
      "index_prefix": "wafer-prod"
    }
  },
  {
    "type": "csv",
    "name": "backup",
    "enabled": true,
    "config": {
      "output_dir": "/backup/wafer-logs",
      "rotation": "daily"
    }
  }
]'
```

### Example 2: Development Setup

Local API only with JSON export for debugging:

```bash
export INTEGRATIONS_CONFIG='[
  {
    "type": "local_api",
    "name": "dev-local",
    "enabled": true,
    "config": {"base_url": "http://localhost:18000"}
  },
  {
    "type": "json",
    "name": "debug-logs",
    "enabled": true,
    "config": {
      "output_dir": "./debug-logs",
      "rotation": "none",
      "pretty_print": true
    }
  }
]'
```

### Example 3: Monitoring-Focused Setup

Send to Zabbix and ELK for monitoring:

```bash
export INTEGRATIONS_CONFIG='[
  {
    "type": "zabbix",
    "name": "zabbix",
    "enabled": true,
    "config": {
      "zabbix_server": "http://zabbix:10051",
      "host": "wafer-fab1"
    }
  },
  {
    "type": "elk",
    "name": "elk-stack",
    "enabled": true,
    "config": {
      "elasticsearch_url": "http://elasticsearch:9200"
    }
  }
]'
```

## Running the Multi-Integration Sidecar

Use the new main file:

```bash
cd apps/sidecar_agent
python main_multi_integration.py
```

Or with Docker:

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .
RUN pip install -e .

ENV INTEGRATIONS_CONFIG='[...]'

CMD ["python", "apps/sidecar_agent/main_multi_integration.py"]
```

## API Endpoints

### POST /v1/ingest/events

Ingest single event to all enabled integrations.

**Response:**
```json
{
  "ok": true,
  "integrations": {
    "primary-db": true,
    "zabbix-prod": true,
    "elasticsearch": false
  }
}
```

### POST /v1/ingest/events:batch

Ingest batch of events.

**Response:**
```json
{
  "ok": true,
  "total": 100,
  "integration_results": {
    "primary-db": {"success": 100, "failed": 0},
    "elasticsearch": {"success": 98, "failed": 2}
  }
}
```

### GET /v1/healthz

Health check with integration status.

**Response:**
```json
{
  "status": "ok",
  "service": "sidecar-agent",
  "version": "3.0.0",
  "spool_count": 0,
  "integrations": {
    "primary-db": {
      "status": "healthy",
      "integration": "primary-db",
      "backend": "local_api"
    },
    "zabbix-prod": {
      "status": "healthy",
      "integration": "zabbix-prod",
      "backend": "zabbix"
    }
  }
}
```

### GET /v1/integrations

List all configured integrations.

**Response:**
```json
{
  "total": 4,
  "enabled": 3,
  "integrations": ["primary-db", "zabbix-prod", "elasticsearch", "csv-backup"],
  "enabled_integrations": ["primary-db", "zabbix-prod", "elasticsearch"]
}
```

## Dependency Injection Pattern

The system uses a dependency injection container for managing integrations:

### Container Lifecycle

```python
from shared_utils.integrations import get_container, IntegrationConfig, IntegrationType

# Get container
container = get_container()

# Register integrations
container.register(IntegrationConfig(
    type=IntegrationType.LOCAL_API,
    name='primary',
    enabled=True,
    config={'base_url': 'http://localhost:18000'}
))

# Initialize all
await container.initialize_all()

# Send events
results = await container.send_event(event_dict)

# Cleanup
await container.close_all()
```

### Custom Integration

Create your own integration by extending `BaseIntegration`:

```python
from shared_utils.integrations.base import BaseIntegration, IntegrationConfig
from typing import Dict, Any, List

class CustomIntegration(BaseIntegration):
    async def initialize(self) -> None:
        # Setup connection
        pass
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        # Send single event
        return True
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        # Send batch
        return {'success': len(events), 'failed': 0}
    
    async def health_check(self) -> Dict[str, Any]:
        # Check health
        return {'status': 'healthy'}
    
    async def close(self) -> None:
        # Cleanup
        pass
```

Register it:

```python
from shared_utils.integrations import IntegrationContainer

# Register custom class
IntegrationContainer.INTEGRATION_REGISTRY['custom'] = CustomIntegration
```

## Troubleshooting

### Integration Not Sending

1. Check if integration is enabled in config
2. Verify health status: `curl http://localhost:8000/v1/healthz`
3. Check logs for error messages
4. Test connectivity to backend

### Partial Failures

Events are spooled if **all** integrations fail. If at least one succeeds, the event is considered delivered.

### Performance

- Each integration sends asynchronously
- Timeouts prevent slow backends from blocking others
- Failed events are retried from spool

### Monitoring

View integration metrics:

```bash
curl http://localhost:8000/metrics | grep integration
```

## Best Practices

1. **Always enable Local API** - Primary storage for queries
2. **Use CSV/JSON for backup** - Local resilience
3. **ELK for analytics** - Long-term trend analysis
4. **Zabbix for alerting** - Real-time monitoring
5. **Webhooks for custom** - Integration with existing systems

## Migration from Original Sidecar

The new multi-integration sidecar is backward compatible. To migrate:

1. Keep existing `main.py` for single Local API integration
2. Use `main_multi_integration.py` for multiple backends
3. Both support same API endpoints
4. Configuration is additive - add integrations without breaking existing setup

