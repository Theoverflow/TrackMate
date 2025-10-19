# Monitoring Component

**Independent CI/CD** | **Version**: 0.2.0

## Overview

The Monitoring Component consists of:
1. **SDK** - Client library for instrumenting applications
2. **Sidecar Agent** - Event collection and forwarding service

## Components

### 1. Monitoring SDK

Python library for monitoring jobs and subjobs.

**Location**: `sdk/monitoring_sdk/`

**Features**:
- Context manager for automatic monitoring
- Parent-child job relationships
- Progress reporting
- Performance metrics (CPU, memory, duration)
- AWS cloud integration (CloudWatch, X-Ray)
- Multi-integration support

**Usage**:
```python
from monitoring_sdk import AppRef, Monitored, SidecarEmitter
from uuid import uuid4

app = AppRef(app_id=uuid4(), name='my-app', version='1.0.0')
emitter = SidecarEmitter(base_url='http://localhost:17000')

with Monitored(site_id='site1', app=app, entity_type='job',
               business_key='daily-batch', emitter=emitter):
    # Your code here
    process_data()
```

### 2. Sidecar Agent

Event collection service that receives monitoring events and forwards to multiple backends.

**Location**: `sidecar/app/`

**Features**:
- HTTP API for event ingestion
- Local event spooling for resilience
- Multi-integration support:
  - Local API
  - AWS CloudWatch + X-Ray
  - Zabbix
  - ELK Stack
  - CSV/JSON export
  - Generic webhooks
- Prometheus metrics endpoint
- Health check endpoint

## Installation

### SDK

```bash
cd components/monitoring
pip install -e ".[dev]"
```

### Sidecar Agent

#### Docker
```bash
docker compose -f ../../deploy/docker-compose/monitoring.yml up -d
```

#### Local Development
```bash
cd components/monitoring/sidecar
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 17000
```

## Configuration

### SDK Configuration

Set via environment variables:
```bash
export SIDECAR_URL=http://localhost:17000
export SITE_ID=site1
```

### Sidecar Configuration

Edit `config/integrations.json`:
```json
[
  {
    "type": "local_api",
    "name": "primary",
    "enabled": true,
    "config": {"base_url": "http://local-api:18000"}
  },
  {
    "type": "aws_cloudwatch",
    "name": "cloudwatch",
    "enabled": true,
    "config": {
      "aws_region": "us-east-1",
      "log_group_name": "/wafer-monitor/jobs",
      "namespace": "WaferMonitor"
    }
  }
]
```

## Testing

```bash
cd components/monitoring
pytest tests/ -v --cov=sdk --cov=sidecar
```

## CI/CD

**GitHub Actions**: `.github/workflows/monitoring.yml`

**Triggers**:
- Push to `main` or `develop`
- Changes to `components/monitoring/**`
- Changes to `shared/**`

**Pipeline**:
1. **Test**: Python 3.10, 3.11, 3.12
2. **Lint**: ruff + mypy
3. **Build**: Docker images for SDK + Sidecar
4. **Push**: ghcr.io registry
5. **Deploy**: Staging environment

## Docker Images

- **SDK**: `ghcr.io/theoverflow/trackmate/monitoring-sdk:latest`
- **Sidecar**: `ghcr.io/theoverflow/trackmate/sidecar-agent:latest`

## API Endpoints

### Sidecar Agent

- `POST /v1/event` - Receive single event
- `POST /v1/events/batch` - Receive batch of events
- `GET /v1/health` - Health check
- `GET /metrics` - Prometheus metrics

## Dependencies

See `pyproject.toml` for full dependency list.

**Core**:
- httpx
- pydantic
- psutil
- tenacity
- structlog

**Optional**:
- boto3 (AWS integration)
- requests (integrations)

## Development

### Setup
```bash
cd components/monitoring
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Run Tests
```bash
pytest tests/ -v
```

### Build Docker Images
```bash
docker build -f Dockerfile.sdk -t monitoring-sdk .
docker build -f Dockerfile.sidecar -t sidecar-agent .
```

## Versioning

**Current Version**: 0.2.0

**Version Strategy**: Independent from other components

## Support

For issues specific to the monitoring component, create an issue with the `component:monitoring` label.

