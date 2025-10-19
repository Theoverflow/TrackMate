# Wafer Monitor v2 — Mission-Critical Monitoring System

**Production-ready monitoring system for semiconductor wafer fabrication with separated environments.**

## 🌟 Features

### Core Capabilities
- ✅ **Real-time Event Ingestion** - High-throughput event processing with local spooling for resilience
- ✅ **Time-Series Storage** - TimescaleDB with 72h hot storage + 10-year S3 archival
- ✅ **Multi-Site Aggregation** - Centralized monitoring across multiple fabrication sites
- ✅ **Performance Metrics** - CPU, memory, duration tracking with automatic collection
- ✅ **Interactive Dashboards** - Real-time Streamlit dashboards with charts and analytics

### Enhanced v2 Features
- 🔥 **Structured Logging** - JSON logging with structured data using structlog
- 🔥 **Distributed Tracing** - OpenTelemetry integration for request tracking across services
- 🔥 **Prometheus Metrics** - Comprehensive metrics collection with /metrics endpoints
- 🔥 **Smart Alerting** - Configurable alert rules with Slack/Webhook/Email notifications
- 🔥 **Error Handling** - Automatic retries with exponential backoff
- 🔥 **Configuration Management** - Pydantic-based config with validation
- 🔥 **Performance Optimized** - Connection pooling, caching, batch processing
- 🔥 **Comprehensive Tests** - Unit, integration, and performance test suites
- 🔥 **Multi-Integration Support** - Send events to multiple backends (Zabbix, ELK, CSV, JSON, Webhooks)
- ☁️ **AWS Cloud Integration** - Monitor EC2, ECS, and Lambda jobs with CloudWatch & X-Ray
- 🗄️ **TimescaleDB Optimization** - Advanced time-series features, compression, retention policies

## 🏗️ Architecture

### Environment Separation

```
┌─────────────────────────────────────────────────────────────────┐
│                     CENTRAL NODE (Env C)                        │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Central Web UI  │◄────────│  Central API     │             │
│  │   (Streamlit)    │         │  (Aggregator)    │             │
│  └──────────────────┘         └─────────┬────────┘             │
│                                          │                       │
└──────────────────────────────────────────┼───────────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
        ┌───────────▼──────────┐  ┌───────▼──────────┐  ┌───────▼──────────┐
        │   SITE 1 (Fab1)      │  │   SITE 2 (Fab2)  │  │   SITE N (FabN)  │
        └──────────────────────┘  └──────────────────┘  └──────────────────┘

Each Site has 3 environments:

┌─────────────────────────────────────────────────────────────────┐
│  ENV A: BUSINESS NODE                                            │
│  ┌──────────────────────────────────────┐                       │
│  │  Sidecar Agent (Forwarding + Spool)  │                       │
│  └───────────────────┬──────────────────┘                       │
└──────────────────────┼──────────────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────────────┐
│  ENV B: PLANT DATA PLANE                                         │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐             │
│  │ Local API  │─▶│ TimescaleDB  │◄─│  Archiver   │──▶ S3       │
│  │ (Ingest +  │  │ (72h hot)    │  │ (Parquet)   │             │
│  │  Query)    │  └──────────────┘  └─────────────┘             │
│  └────────────┘                                                  │
└──────────────────────────────────────────────────────────────────┘
         │
         │ Read-only
┌────────▼─────────────────────────────────────────────────────────┐
│  ENV C: OPERATOR HMI                                             │
│  ┌────────────────────────────────────┐                         │
│  │  Local Web UI (Streamlit)          │                         │
│  └────────────────────────────────────┘                         │
└──────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ with TimescaleDB extension
- (Optional) S3-compatible storage for archival
- (Optional) OpenTelemetry collector for tracing

### Installation

```bash
# Clone repository
git clone <repo-url>
cd wafer-monitor-v2

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"
```

### Configuration

Create `.env` files or set environment variables:

#### Sidecar Agent
```env
LOCAL_API_BASE=http://localhost:18000
SPOOL_DIR=/tmp/sidecar-spool
LOG_LEVEL=INFO
ENABLE_TRACING=true
OTLP_ENDPOINT=http://localhost:4317
```

#### Local API
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/monitor
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=10
LOG_LEVEL=INFO
ENABLE_TRACING=true
```

#### Central API
```env
SITES=fab1=http://site1:18000,fab2=http://site2:18000
LOG_LEVEL=INFO
```

### Running Services

#### Using Python directly

```bash
# Start Local API
cd apps/local_api
python main.py

# Start Sidecar Agent
cd apps/sidecar_agent
python main.py

# Start Central API
cd apps/central_api
python main.py

# Start Archiver
cd apps/archiver
python main.py

# Start Web UI (Local)
cd apps/web_local
streamlit run streamlit_app.py --server.port 8501

# Start Web UI (Central)
cd apps/web_central
streamlit run streamlit_app.py --server.port 8502
```

#### Using Docker Compose

```bash
# Local site deployment
docker-compose -f deploy/docker/compose.local-data.yml up -d
docker-compose -f deploy/docker/compose.local-web.yml up -d

# Central deployment
docker-compose -f deploy/docker/compose.central.yml up -d

# Business node
docker-compose -f deploy/docker/compose.business.yml up -d
```

#### Using Podman

```bash
# See deploy/podman/ for pod scripts
cd deploy/podman/local-data
./up.sh
```

## 📊 Monitoring SDK Usage

### Basic Usage

```python
from uuid import uuid4
from monitoring_sdk import Monitored, AppRef, SidecarEmitter

# Create app reference
app = AppRef(
    app_id=uuid4(),
    name='wafer-process',
    version='2.1.0'
)

# Monitor a job
with Monitored(
    site_id='fab1',
    app=app,
    entity_type='job',
    business_key='batch-12345'
):
    # Your processing code here
    process_wafer_batch()
```

### Advanced Usage with Subjobs

```python
# Monitor parent job with subjobs
with Monitored(
    site_id='fab1',
    app=app,
    entity_type='job',
    business_key='batch-12345',
    metadata={'priority': 'high', 'customer': 'ACME'}
) as job:
    
    # Process multiple subjobs
    for wafer_id in wafer_ids:
        with Monitored(
            site_id='fab1',
            app=app,
            entity_type='subjob',
            parent_id=job.entity_id,
            sub_key=f'wafer-{wafer_id}'
        ) as subjob:
            process_wafer(wafer_id)
            
            # Report progress
            subjob.tick(extra_meta={'progress': 0.5})
```

### Custom Emitter Configuration

```python
from monitoring_sdk import SidecarEmitter

# Custom emitter with retry configuration
emitter = SidecarEmitter(
    base_url='http://sidecar:8000',
    timeout=10.0,
    max_retries=5,
    enable_retries=True
)

with Monitored(
    site_id='fab1',
    app=app,
    entity_type='job',
    emitter=emitter
):
    process_data()
```

## 🔍 API Endpoints

### Sidecar Agent (Port 8000)

- `POST /v1/ingest/events` - Ingest single event
- `POST /v1/ingest/events:batch` - Ingest batch of events
- `GET /v1/healthz` - Health check
- `GET /metrics` - Prometheus metrics

### Local API (Port 18000)

- `POST /v1/ingest/events` - Ingest single event (from sidecar)
- `POST /v1/ingest/events:batch` - Ingest batch of events
- `GET /v1/jobs` - Query jobs with filters
- `GET /v1/subjobs` - Query subjobs with filters
- `GET /v1/stream` - Real-time event stream (SSE)
- `GET /v1/healthz` - Health check
- `GET /metrics` - Prometheus metrics

### Central API (Port 19000)

- `GET /v1/jobs?site=<site_id>` - Query jobs from specific site
- `GET /v1/subjobs?site=<site_id>` - Query subjobs from specific site
- `GET /v1/sites` - List configured sites
- `GET /v1/healthz` - Health check with site status
- `GET /metrics` - Prometheus metrics

## 📈 Metrics & Observability

### Prometheus Metrics

All services expose `/metrics` endpoints with comprehensive metrics:

**HTTP Metrics:**
- `http_requests_total` - Total HTTP requests by method, endpoint, status
- `http_request_duration_seconds` - Request latency histogram

**Database Metrics:**
- `db_operations_total` - Total DB operations by type, table, status
- `db_operation_duration_seconds` - DB operation latency
- `db_pool_size` - Connection pool size
- `db_pool_available` - Available connections

**Event Processing:**
- `events_processed_total` - Total events by type and status
- `events_in_spool` - Current spool directory size

**Job Metrics:**
- `jobs_total` - Total jobs by app and status
- `job_duration_seconds` - Job duration histogram

### Distributed Tracing

Enable OpenTelemetry tracing by setting:

```env
ENABLE_TRACING=true
OTLP_ENDPOINT=http://your-collector:4317
```

Traces include:
- Request flows across services
- Database operations
- Event forwarding
- Query execution

View traces in Jaeger, Tempo, or any OTLP-compatible backend.

### Structured Logging

All services emit structured JSON logs:

```json
{
  "event": "event_ingested",
  "timestamp": "2025-10-19T12:34:56.789Z",
  "level": "info",
  "service": "local-api",
  "event_kind": "finished",
  "entity_type": "job",
  "site_id": "fab1",
  "duration_s": 0.0234
}
```

## 🚨 Alerting

### Default Alert Rules

The system includes built-in alert rules:

1. **High Failure Rate** - >10% jobs failing
2. **Long Running Jobs** - Jobs running >1 hour
3. **High Memory Usage** - >8GB memory usage
4. **No Jobs Received** - No activity when expected
5. **Ingestion Lag** - >100 events in spool
6. **Database Issues** - Connection failures

### Configure Alerts

Set environment variables:

```env
# Webhook alerts
ALERT_WEBHOOK_URL=https://your-webhook-endpoint

# Slack alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Email alerts (requires email API)
EMAIL_API_URL=https://your-email-api
```

### Custom Alert Rules

```python
from shared_utils import get_alert_manager, AlertRule, AlertSeverity

alert_mgr = get_alert_manager()

# Add custom rule
alert_mgr.add_rule(AlertRule(
    name='custom_metric_threshold',
    condition=lambda m: m.get('custom_metric', 0) > 1000,
    severity=AlertSeverity.WARNING,
    message_template='Custom metric exceeded: {custom_metric}',
    cooldown_minutes=10
))
```

## 🧪 Testing

### Run Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires running services)
pytest tests/integration/ -v

# Performance tests
pytest tests/performance/ -v -s -m performance

# All tests with coverage
pytest tests/ --cov=apps --cov-report=html
```

### Performance Benchmarks

Expected performance (adjust based on hardware):

- **Single Event Latency**: <500ms average, <1s P95
- **Batch Throughput**: >50 events/second
- **Concurrent Load**: >100 events/second with 20 concurrent clients
- **Query Latency**: <200ms average for 100 jobs

## 📁 Project Structure

```
wafer-monitor-v2/
├── apps/
│   ├── archiver/           # S3 archival service
│   ├── central_api/        # Central aggregation API
│   ├── local_api/          # Local site API
│   ├── monitoring_sdk/     # Client SDK
│   │   └── aws_helpers.py  # AWS platform helpers
│   ├── sidecar_agent/      # Event forwarding agent
│   ├── shared_utils/       # Shared utilities
│   │   ├── alerts.py       # Alerting system
│   │   ├── config.py       # Configuration
│   │   ├── logging.py      # Structured logging
│   │   ├── metrics.py      # Prometheus metrics
│   │   ├── tracing.py      # OpenTelemetry tracing
│   │   └── integrations/   # Multi-backend integrations
│   │       ├── local_api.py       # Local API integration
│   │       ├── zabbix.py          # Zabbix monitoring
│   │       ├── elk.py             # Elasticsearch/Logstash
│   │       ├── csv_export.py     # CSV file export
│   │       ├── json_export.py    # JSON file export
│   │       ├── webhook.py        # Generic webhooks
│   │       ├── aws_cloudwatch.py # AWS CloudWatch
│   │       ├── aws_xray.py       # AWS X-Ray tracing
│   │       └── container.py      # DI container
│   ├── web_central/        # Central dashboard
│   └── web_local/          # Local site dashboard
├── deploy/
│   ├── docker/             # Docker Compose configs
│   └── podman/             # Podman pod scripts
├── docs/                   # Documentation
│   ├── API.md              # API reference
│   ├── DEPLOYMENT.md       # Deployment guide
│   ├── INTEGRATIONS.md     # Integration docs
│   ├── MULTI_INTEGRATION_GUIDE.md
│   ├── AWS_INTEGRATION.md  # AWS cloud guide
│   └── TIMESCALEDB_OPTIMIZATION.md
├── examples/
│   ├── integrations/       # Integration configs
│   └── aws/                # AWS examples
│       ├── lambda_handler.py
│       ├── ec2_job.py
│       ├── ecs_task.py
│       ├── Dockerfile.lambda
│       ├── Dockerfile.ec2
│       ├── task-definition.json
│       └── IAM-policies.json
├── ops/
│   ├── sql/
│   │   ├── schema.sql      # Database schema
│   │   ├── timescaledb_enhancements.sql
│   │   └── timescaledb_config.sql
│   └── scripts/
│       ├── monitor_timescaledb.py
│       └── maintenance.sh
├── tests/
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── performance/        # Performance tests
├── pyproject.toml          # Dependencies
└── README.md               # This file
```

## 🔧 Database Schema

### Tables

- **app** - Application registry
- **job** - Job records (hypertable, 72h retention)
- **subjob** - Subjob records (hypertable, 72h retention)
- **event** - Raw events (hypertable, 72h retention)

### Indexes

- Time-based indexes for efficient queries
- Status indexes for filtering
- Unique constraint on idempotency keys

## 🎯 Performance Optimization

### Built-in Optimizations

1. **Connection Pooling** - Async connection pools with configurable sizes
2. **Query Optimization** - Indexed queries with CTEs for deduplication
3. **Batch Processing** - Batch event ingestion support
4. **Caching** - Dashboard caching with configurable TTL
5. **Retry Logic** - Automatic retries with exponential backoff
6. **Spooling** - Local event spooling for resilience

### Tuning Tips

```env
# Database pool sizing
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20

# Query limits
QUERY_DEFAULT_LIMIT=1000
QUERY_MAX_LIMIT=10000

# Timeouts
REQUEST_TIMEOUT_S=5.0
DRAIN_INTERVAL_S=2.0
```

## 🐛 Troubleshooting

### Check Service Health

```bash
# Sidecar Agent
curl http://localhost:8000/v1/healthz

# Local API
curl http://localhost:18000/v1/healthz

# Central API
curl http://localhost:19000/v1/healthz
```

### View Metrics

```bash
# View Prometheus metrics
curl http://localhost:8000/metrics
```

### Check Spool Directory

```bash
# View spooled events (when Local API is unavailable)
ls -l /tmp/sidecar-spool/
```

### Database Connectivity

```bash
# Connect to database
psql $DATABASE_URL

# Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE schemaname = 'public';
```

## ☁️ AWS Cloud Integration

Monitor near-real-time compute jobs on **AWS EC2**, **ECS**, and **Lambda** with CloudWatch and X-Ray integration!

### Quick Start

```python
from monitoring_sdk import AppRef, Monitored
from monitoring_sdk.aws_helpers import create_aws_emitter, get_aws_metadata
from uuid import uuid4

app = AppRef(app_id=uuid4(), name="my-aws-job", version="1.0.0")
emitter = create_aws_emitter()  # Auto-detects EC2/ECS/Lambda
metadata = get_aws_metadata()

with Monitored(
    site_id='site1',
    app=app,
    entity_type='job',
    business_key='daily-batch',
    emitter=emitter,
    metadata=metadata
):
    # Your job logic - metrics sent to CloudWatch & X-Ray
    process_data()
```

### Lambda Decorator

```python
from monitoring_sdk.aws_helpers import monitored_lambda_handler

@monitored_lambda_handler('site1', app_ref)
def lambda_handler(event, context):
    # Automatically monitored!
    return {'statusCode': 200}
```

**See [AWS_INTEGRATION.md](AWS_INTEGRATION_SUMMARY.md) for complete guide.**

## 🔌 Multi-Integration Support

Send monitoring events to multiple backends simultaneously:

- **Local API** - TimescaleDB storage
- **Zabbix** - Enterprise monitoring
- **ELK Stack** - Elasticsearch for search & analysis
- **CSV/JSON Export** - File-based backups
- **Webhooks** - Generic HTTP endpoints
- **AWS CloudWatch** - Cloud metrics & logs
- **AWS X-Ray** - Distributed tracing

**See [INTEGRATIONS.md](docs/INTEGRATIONS.md) and [MULTI_INTEGRATION_GUIDE.md](docs/MULTI_INTEGRATION_GUIDE.md) for details.**

## 🗄️ TimescaleDB Enhancements

Advanced time-series database features:

- **Continuous Aggregates** - Pre-computed rollups (1h, 1d, 1w, 1mo)
- **Compression** - Automatic compression after 3 days
- **Retention Policies** - Auto-delete data after 90 days
- **Stored Procedures** - Analytics & alerting functions
- **Monitoring Views** - Health & performance metrics

**See [TIMESCALEDB_OPTIMIZATION.md](docs/TIMESCALEDB_OPTIMIZATION.md) for complete guide.**

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - 10-minute setup guide
- **[API.md](docs/API.md)** - Complete API reference
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment guide
- **[INTEGRATIONS.md](docs/INTEGRATIONS.md)** - Integration backends
- **[AWS_INTEGRATION.md](docs/AWS_INTEGRATION.md)** - AWS cloud monitoring
- **[TIMESCALEDB_OPTIMIZATION.md](docs/TIMESCALEDB_OPTIMIZATION.md)** - Database optimization
- **[CHANGELOG.md](CHANGELOG.md)** - Version history

## 📝 License

[Your License Here]

## 🤝 Contributing

[Contribution guidelines here]

## 📧 Support

[Support information here]
