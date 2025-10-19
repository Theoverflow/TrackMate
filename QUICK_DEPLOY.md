# Quick Deploy Guide - 3-Component Architecture

## Deploy All Components

```bash
# Deploy full stack
docker compose -f deploy/docker-compose/monitoring.yml up -d
docker compose -f deploy/docker-compose/data-plane.yml up -d
docker compose -f deploy/docker-compose/web.yml up -d

# Verify all services
curl http://localhost:17000/v1/health    # Sidecar
curl http://localhost:18000/v1/healthz   # Local API
curl http://localhost:19000/v1/healthz   # Central API
curl http://localhost:8501/_stcore/health # Local Dashboard
curl http://localhost:8502/_stcore/health # Central Dashboard
```

## Deploy Individual Components

### 1. Monitoring Component Only

```bash
cd deploy/docker-compose
docker compose -f monitoring.yml up -d

# Access
# Sidecar API: http://localhost:17000
# Metrics: http://localhost:8000/metrics
```

### 2. Data Plane Component Only

```bash
cd deploy/docker-compose
docker compose -f data-plane.yml up -d

# Access
# Local API: http://localhost:18000
# Central API: http://localhost:19000
# TimescaleDB: localhost:5432
```

### 3. Web Component Only

```bash
cd deploy/docker-compose
docker compose -f web.yml up -d

# Access
# Local Dashboard: http://localhost:8501
# Central Dashboard: http://localhost:8502
```

## Stop Components

```bash
# Stop individual component
docker compose -f deploy/docker-compose/monitoring.yml down
docker compose -f deploy/docker-compose/data-plane.yml down
docker compose -f deploy/docker-compose/web.yml down

# Stop all
docker compose -f deploy/docker-compose/monitoring.yml down
docker compose -f deploy/docker-compose/data-plane.yml down
docker compose -f deploy/docker-compose/web.yml down
```

## Development Setup

### Monitoring Component

```bash
cd components/monitoring
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run sidecar
cd sidecar
uvicorn app.main:app --reload --port 17000
```

### Data Plane Component

```bash
cd components/data-plane
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run local API
cd local-api
uvicorn app.main:app --reload --port 18000

# Run central API
cd central-api
uvicorn app.main:app --reload --port 19000
```

### Web Component

```bash
cd components/web
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run local dashboard
cd local-dashboard
streamlit run app/streamlit_app.py --server.port=8501

# Run central dashboard
cd central-dashboard
streamlit run app/streamlit_app.py --server.port=8502
```

## Test Components

```bash
# Test monitoring
cd components/monitoring
pytest tests/ -v

# Test data plane
cd components/data-plane
pytest tests/ -v

# Test web
cd components/web
pytest tests/ -v

# Test all
pytest tests/integration/ -v
```

## Build Docker Images

```bash
# Build monitoring images
cd components/monitoring
docker build -f Dockerfile.sdk -t monitoring-sdk .
docker build -f Dockerfile.sidecar -t sidecar-agent .

# Build data plane images
cd components/data-plane
docker build -f Dockerfile.local-api -t local-api .
docker build -f Dockerfile.central-api -t central-api .
docker build -f Dockerfile.archiver -t archiver .

# Build web images
cd components/web
docker build -f Dockerfile.local-dashboard -t local-dashboard .
docker build -f Dockerfile.central-dashboard -t central-dashboard .
```

## Common Commands

### Health Checks

```bash
# Check all services
./scripts/health-check.sh

# Or manually
curl -f http://localhost:17000/v1/health || echo "Sidecar DOWN"
curl -f http://localhost:18000/v1/healthz || echo "Local API DOWN"
curl -f http://localhost:19000/v1/healthz || echo "Central API DOWN"
```

### View Logs

```bash
# Monitoring logs
docker compose -f deploy/docker-compose/monitoring.yml logs -f

# Data plane logs
docker compose -f deploy/docker-compose/data-plane.yml logs -f sidecar-agent
docker compose -f deploy/docker-compose/data-plane.yml logs -f local-api

# Web logs
docker compose -f deploy/docker-compose/web.yml logs -f local-dashboard
```

### Database Operations

```bash
# Connect to TimescaleDB
docker exec -it wafer-timescaledb psql -U wafer -d wafer_local

# Run migrations
docker exec -it wafer-timescaledb psql -U wafer -d wafer_local -f /sql/schema.sql

# Backup database
docker exec wafer-timescaledb pg_dump -U wafer wafer_local > backup.sql
```

## Configuration

### Environment Variables

Create `.env` files for each component:

**Monitoring** (`.env.monitoring`):
```bash
INTEGRATION_CONFIG=/config/integrations.json
LOG_LEVEL=INFO
PROMETHEUS_PORT=8000
```

**Data Plane** (`.env.data-plane`):
```bash
DATABASE_URL=postgresql://wafer:wafer@timescaledb:5432/wafer_local
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20
LOG_LEVEL=INFO
```

**Web** (`.env.web`):
```bash
LOCAL_API_URL=http://local-api:18000
CENTRAL_API_URL=http://central-api:19000
REFRESH_INTERVAL_S=5
LOG_LEVEL=INFO
```

### Use Environment Files

```bash
docker compose -f deploy/docker-compose/monitoring.yml --env-file .env.monitoring up -d
docker compose -f deploy/docker-compose/data-plane.yml --env-file .env.data-plane up -d
docker compose -f deploy/docker-compose/web.yml --env-file .env.web up -d
```

## Scaling

### Scale Individual Services

```bash
# Scale sidecar agents
docker compose -f deploy/docker-compose/monitoring.yml up -d --scale sidecar-agent=3

# Scale local APIs
docker compose -f deploy/docker-compose/data-plane.yml up -d --scale local-api=3

# Scale dashboards
docker compose -f deploy/docker-compose/web.yml up -d --scale local-dashboard=2
```

## Troubleshooting

### Services Not Starting

```bash
# Check logs
docker compose -f deploy/docker-compose/monitoring.yml logs

# Check container status
docker compose -f deploy/docker-compose/monitoring.yml ps

# Restart service
docker compose -f deploy/docker-compose/monitoring.yml restart sidecar-agent
```

### Network Issues

```bash
# Verify networks
docker network ls | grep wafer

# Inspect network
docker network inspect wafer-monitoring
docker network inspect wafer-data-plane
docker network inspect wafer-web
```

### Port Conflicts

If ports are already in use, edit docker-compose files to change port mappings:
```yaml
ports:
  - "27000:17000"  # Changed from 17000:17000
```

## Production Deployment

### Using Production Overrides

```bash
docker compose -f deploy/docker-compose/monitoring.yml \
               -f deploy/docker-compose/monitoring.prod.yml up -d
```

### Kubernetes

```bash
# Deploy using Helm
helm install monitoring ./deploy/helm/monitoring -f values.prod.yaml
helm install data-plane ./deploy/helm/data-plane -f values.prod.yaml
helm install web ./deploy/helm/web -f values.prod.yaml
```

## Monitoring the System

### Prometheus Metrics

```bash
# Scrape metrics
curl http://localhost:8000/metrics    # Sidecar
curl http://localhost:18000/metrics   # Local API
```

### Grafana Dashboards

Access pre-configured dashboards at: http://localhost:3000

## Quick Links

- **Monitoring**: [README](components/monitoring/README.md)
- **Data Plane**: [README](components/data-plane/README.md)
- **Web**: [README](components/web/README.md)
- **Architecture**: [RESTRUCTURE_SUMMARY.md](RESTRUCTURE_SUMMARY.md)
- **Main README**: [README.md](README.md)

