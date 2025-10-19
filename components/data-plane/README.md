# Data Plane Component

**Independent CI/CD** | **Version**: 0.2.0

## Overview

The Data Plane Component handles data persistence and API access:
1. **Local API** - Site-level event ingestion and querying
2. **Central API** - Multi-site aggregation
3. **Archiver** - Long-term storage to S3/Parquet
4. **TimescaleDB** - Time-series database

## Components

### 1. Local API

FastAPI service for event ingestion and query at site level.

**Location**: `local-api/app/`

**Features**:
- Event ingestion (single + batch)
- Job/subjob querying
- TimescaleDB integration
- Connection pooling
- Query result caching
- OpenTelemetry tracing
- Prometheus metrics

**Endpoints**:
- `POST /v1/event` - Ingest event
- `POST /v1/events/batch` - Batch ingest
- `GET /v1/jobs` - Query jobs
- `GET /v1/subjobs` - Query subjobs
- `GET /v1/healthz` - Health check
- `GET /metrics` - Prometheus metrics

### 2. Central API

Aggregation service for multi-site monitoring.

**Location**: `central-api/app/`

**Features**:
- Multi-site job aggregation
- Cross-site queries
- Health aggregation
- Site status monitoring

**Endpoints**:
- `GET /v1/jobs/aggregate` - Aggregate jobs across sites
- `GET /v1/sites/health` - Site health status
- `GET /v1/healthz` - Health check

### 3. Archiver

Background service for archiving old data.

**Location**: `archiver/app/`

**Features**:
- Automatic archival after 72h
- Parquet format for efficiency
- S3-compatible storage
- Configurable retention
- Compression

### 4. TimescaleDB

Time-series database with advanced features.

**Location**: `database/`

**Features**:
- Hypertables for job/subjob/event
- Continuous aggregates (1h, 1d, 1w, 1mo)
- Automatic compression after 3 days
- Retention policies (90 days)
- Performance indexes
- Stored procedures for analytics

## Installation

### Full Stack (Docker Compose)

```bash
docker compose -f ../../deploy/docker-compose/data-plane.yml up -d
```

### Individual Services

#### Local API
```bash
cd components/data-plane/local-api
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 18000
```

#### Central API
```bash
cd components/data-plane/central-api
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 19000
```

#### Archiver
```bash
cd components/data-plane/archiver
pip install -r requirements.txt
python app/main.py
```

## Configuration

### Environment Variables

**Local API**:
```bash
DATABASE_URL=postgresql://wafer:wafer@localhost:5432/wafer_local
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20
LOG_LEVEL=INFO
```

**Central API**:
```bash
SITE_URLS=http://site1-api:18000,http://site2-api:18000
LOG_LEVEL=INFO
```

**Archiver**:
```bash
DATABASE_URL=postgresql://wafer:wafer@localhost:5432/wafer_local
S3_BUCKET=wafer-archive
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
ARCHIVE_INTERVAL_HOURS=24
```

### Database Setup

```bash
# Initialize schema
psql $DATABASE_URL -f database/sql/schema.sql

# Apply TimescaleDB enhancements
psql $DATABASE_URL -f database/sql/timescaledb_enhancements.sql

# Apply configuration
psql $DATABASE_URL -f database/sql/timescaledb_config.sql
```

## Testing

```bash
cd components/data-plane
pytest tests/ -v --cov=.
```

**Integration Tests** (requires running database):
```bash
docker compose -f ../../deploy/docker-compose/data-plane.yml up -d timescaledb
pytest tests/integration/ -v
```

## CI/CD

**GitHub Actions**: `.github/workflows/data-plane.yml`

**Triggers**:
- Push to `main` or `develop`
- Changes to `components/data-plane/**`
- Changes to `shared/**`

**Pipeline**:
1. **Test**: Python 3.10, 3.11, 3.12 with PostgreSQL
2. **Lint**: ruff + mypy
3. **Build**: Docker images for all services
4. **Push**: ghcr.io registry
5. **Deploy**: Staging environment

**Database Integration**:
- PostgreSQL/TimescaleDB service in CI
- Automatic schema setup
- Integration tests with real database

## Docker Images

- **Local API**: `ghcr.io/theoverflow/trackmate/local-api:latest`
- **Central API**: `ghcr.io/theoverflow/trackmate/central-api:latest`
- **Archiver**: `ghcr.io/theoverflow/trackmate/archiver:latest`

## Database Schema

### Tables

- **app** - Application registry
- **job** - Job records (hypertable, 72h retention)
- **subjob** - Subjob records (hypertable, 72h retention)
- **event** - Raw events (hypertable, 72h retention)

### Continuous Aggregates

- **job_hourly_stats** - Hourly job statistics
- **job_daily_stats** - Daily job statistics
- **job_weekly_stats** - Weekly job statistics
- **job_monthly_stats** - Monthly job statistics

### Views

- **job_health_summary** - Real-time health metrics
- **slow_queries** - Slow query detection
- **compression_status** - Compression monitoring

### Stored Procedures

- `calculate_job_metrics()` - Job analytics
- `detect_anomalies()` - Anomaly detection
- `generate_alerts()` - Alert generation

## Monitoring

### Database Health

```bash
# Run monitoring script
cd components/data-plane/database
python scripts/monitor_timescaledb.py
```

### Maintenance

```bash
# Run maintenance tasks
cd components/data-plane/database
./scripts/maintenance.sh
```

### Performance Tuning

See `database/sql/timescaledb_config.sql` for optimized PostgreSQL settings.

## Dependencies

See `pyproject.toml` for full dependency list.

**Core**:
- fastapi
- uvicorn
- asyncpg
- pandas
- pyarrow

**Optional**:
- boto3 (S3 archival)
- opentelemetry (tracing)

## Development

### Setup
```bash
cd components/data-plane
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
docker build -f Dockerfile.local-api -t local-api .
docker build -f Dockerfile.central-api -t central-api .
docker build -f Dockerfile.archiver -t archiver .
```

## Versioning

**Current Version**: 0.2.0

**Version Strategy**: Independent from other components

## Support

For issues specific to the data plane component, create an issue with the `component:data-plane` label.

