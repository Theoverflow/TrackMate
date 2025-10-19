# Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Setup](#database-setup)
4. [Service Deployment](#service-deployment)
5. [Monitoring & Observability](#monitoring--observability)
6. [Production Considerations](#production-considerations)

## Prerequisites

### Software Requirements

- Python 3.10 or higher
- PostgreSQL 14+ with TimescaleDB extension
- (Optional) Docker/Podman for containerized deployment
- (Optional) S3-compatible storage for archival
- (Optional) OpenTelemetry Collector for tracing
- (Optional) Prometheus for metrics collection

### Hardware Recommendations

**Local API Server (per site):**
- CPU: 4+ cores
- RAM: 8GB minimum, 16GB recommended
- Storage: SSD with 100GB+ for database

**Sidecar Agent (per business node):**
- CPU: 2 cores
- RAM: 2GB
- Storage: 10GB for spool directory

**Central API:**
- CPU: 2 cores
- RAM: 4GB

## Environment Setup

### 1. Clone and Install

```bash
git clone <repo-url>
cd wafer-monitor-v2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"
```

### 2. Configuration Files

Create `.env` files for each service or use environment variables.

#### Example: `.env.sidecar`

```env
# Service identification
SERVICE_NAME=sidecar-agent
SERVICE_VERSION=2.0.0
ENVIRONMENT=production

# Logging
LOG_LEVEL=INFO
JSON_LOGS=true

# Tracing
ENABLE_TRACING=true
OTLP_ENDPOINT=http://otel-collector:4317

# Service configuration
LOCAL_API_BASE=http://local-api:18000
SPOOL_DIR=/var/lib/sidecar-spool
DRAIN_INTERVAL_S=2.0
REQUEST_TIMEOUT_S=5.0
MAX_BATCH_SIZE=100
```

#### Example: `.env.local_api`

```env
# Service identification
SERVICE_NAME=local-api
SERVICE_VERSION=2.0.0
ENVIRONMENT=production

# Logging
LOG_LEVEL=INFO
JSON_LOGS=true

# Tracing
ENABLE_TRACING=true
OTLP_ENDPOINT=http://otel-collector:4317

# Database
DATABASE_URL=postgresql://monitor:secure_password@postgres:5432/monitor
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20
MAX_SKEW_S=600
QUERY_DEFAULT_LIMIT=1000
QUERY_MAX_LIMIT=10000
```

#### Example: `.env.central_api`

```env
# Service identification
SERVICE_NAME=central-api
SERVICE_VERSION=2.0.0
ENVIRONMENT=production

# Logging
LOG_LEVEL=INFO
JSON_LOGS=true

# Sites configuration
SITES=fab1=http://site1-local-api:18000,fab2=http://site2-local-api:18000
REQUEST_TIMEOUT_S=3.0
CACHE_TTL_S=30
```

#### Example: `.env.archiver`

```env
# Service identification
SERVICE_NAME=archiver
SERVICE_VERSION=2.0.0
ENVIRONMENT=production

# Logging
LOG_LEVEL=INFO
JSON_LOGS=true

# Database
DATABASE_URL=postgresql://monitor:secure_password@postgres:5432/monitor

# S3 configuration
S3_BUCKET=wafer-monitor-archive
S3_PREFIX=monitoring/
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-west-2

# Archival settings
SITE_ID=fab1
ARCHIVE_INTERVAL_HOURS=1
RETENTION_HOURS=72
```

## Database Setup

### 1. Install TimescaleDB

```bash
# Ubuntu/Debian
sudo apt-get install timescaledb-postgresql-14

# Or use Docker
docker run -d --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  timescale/timescaledb:latest-pg14
```

### 2. Initialize Database

```bash
# Connect to PostgreSQL
psql -U postgres -h localhost

# Create database
CREATE DATABASE monitor;

# Connect to the database
\c monitor

# Run schema
\i ops/sql/schema.sql
```

### 3. Verify Setup

```sql
-- Check TimescaleDB extension
SELECT * FROM timescaledb_information.hypertables;

-- Should show job, subjob, and event hypertables
```

## Service Deployment

### Option 1: Python Services

#### Start Services Individually

```bash
# Terminal 1: Local API
cd apps/local_api
python main.py

# Terminal 2: Sidecar Agent
cd apps/sidecar_agent
python main.py

# Terminal 3: Central API
cd apps/central_api
python main.py

# Terminal 4: Archiver (optional, scheduled)
cd apps/archiver
python main.py

# Terminal 5: Local Web UI
cd apps/web_local
streamlit run streamlit_app.py --server.port 8501

# Terminal 6: Central Web UI
cd apps/web_central
streamlit run streamlit_app.py --server.port 8502
```

#### Using systemd (Linux)

Create service files in `/etc/systemd/system/`:

**`/etc/systemd/system/wafer-monitor-local-api.service`:**

```ini
[Unit]
Description=Wafer Monitor Local API
After=network.target postgresql.service

[Service]
Type=simple
User=monitor
WorkingDirectory=/opt/wafer-monitor/apps/local_api
EnvironmentFile=/opt/wafer-monitor/.env.local_api
ExecStart=/opt/wafer-monitor/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wafer-monitor-local-api
sudo systemctl start wafer-monitor-local-api
sudo systemctl status wafer-monitor-local-api
```

### Option 2: Docker Compose

```bash
# Local site deployment
docker-compose -f deploy/docker/compose.local-data.yml up -d
docker-compose -f deploy/docker/compose.local-web.yml up -d

# Business node
docker-compose -f deploy/docker/compose.business.yml up -d

# Central node
docker-compose -f deploy/docker/compose.central.yml up -d
```

### Option 3: Kubernetes

Example deployment (create your own manifests):

```yaml
# local-api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: local-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: local-api
  template:
    metadata:
      labels:
        app: local-api
    spec:
      containers:
      - name: local-api
        image: wafer-monitor/local-api:2.0.0
        ports:
        - containerPort: 18000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        - name: LOG_LEVEL
          value: "INFO"
        - name: ENABLE_TRACING
          value: "true"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
```

## Monitoring & Observability

### Prometheus Setup

**prometheus.yml:**

```yaml
scrape_configs:
  - job_name: 'sidecar-agent'
    static_configs:
      - targets: ['sidecar:8000']
  
  - job_name: 'local-api'
    static_configs:
      - targets: ['local-api:18000']
  
  - job_name: 'central-api'
    static_configs:
      - targets: ['central-api:19000']
```

### OpenTelemetry Collector

**otel-collector-config.yaml:**

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  
  logging:
    loglevel: debug

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger, logging]
```

### Grafana Dashboards

Import dashboards from `docs/grafana-dashboards/` (create these based on your metrics).

### Alert Manager

Configure Slack/Email notifications:

```env
ALERT_WEBHOOK_URL=https://your-alert-endpoint
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
EMAIL_API_URL=https://your-email-service
```

## Production Considerations

### Security

1. **Database Credentials:**
   - Use strong passwords
   - Rotate credentials regularly
   - Use SSL/TLS for database connections

2. **API Authentication:**
   - Add API keys or OAuth for production
   - Use HTTPS for all endpoints
   - Implement rate limiting

3. **Network Segmentation:**
   - Isolate business nodes (Env A)
   - Restrict data plane access (Env B)
   - Firewall rules for HMI nodes (Env C)

### High Availability

1. **Database:**
   - Use PostgreSQL replication
   - Configure TimescaleDB for HA
   - Regular backups

2. **Services:**
   - Run multiple replicas
   - Use load balancers
   - Health check endpoints

3. **Storage:**
   - S3 with versioning for archives
   - Redundant spool directories

### Performance Tuning

1. **Database:**
   ```sql
   -- Tune PostgreSQL settings
   ALTER SYSTEM SET shared_buffers = '2GB';
   ALTER SYSTEM SET effective_cache_size = '6GB';
   ALTER SYSTEM SET work_mem = '50MB';
   ALTER SYSTEM SET maintenance_work_mem = '512MB';
   ```

2. **Connection Pooling:**
   - Adjust pool sizes based on load
   - Monitor pool utilization

3. **Caching:**
   - Use Redis for query caching (optional enhancement)
   - Configure dashboard cache TTL

### Backup & Recovery

1. **Database Backups:**
   ```bash
   # Daily backups
   pg_dump -U monitor -h localhost monitor > backup_$(date +%Y%m%d).sql
   
   # Restore
   psql -U monitor -h localhost monitor < backup_20251019.sql
   ```

2. **S3 Archives:**
   - Enable versioning
   - Configure lifecycle policies
   - Test restore procedures

### Monitoring Checklist

- [ ] Prometheus scraping all services
- [ ] Grafana dashboards configured
- [ ] Alerts configured and tested
- [ ] Log aggregation setup (ELK, Loki, etc.)
- [ ] Tracing collector running
- [ ] Health checks passing
- [ ] Backup procedures tested

## Troubleshooting

### Service Won't Start

1. Check logs: `journalctl -u wafer-monitor-* -f`
2. Verify configuration
3. Check database connectivity
4. Ensure ports are available

### High Latency

1. Check database performance
2. Monitor connection pool utilization
3. Review query execution plans
4. Check network latency between services

### Events Not Appearing

1. Check spool directory for stuck events
2. Verify Sidecar Agent → Local API connectivity
3. Check database write performance
4. Review logs for errors

### Memory Issues

1. Adjust connection pool sizes
2. Review query result limits
3. Monitor long-running queries
4. Check for memory leaks in logs

