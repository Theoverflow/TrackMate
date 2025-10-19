# Quick Start Guide

Get the Wafer Monitor system running in under 10 minutes!

## Prerequisites

- Python 3.10+
- PostgreSQL with TimescaleDB
- 15 minutes ⏱️

## Step 1: Install Dependencies

```bash
# Clone and enter directory
cd wafer-monitor-v2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate on Windows

# Install
pip install -e .
```

## Step 2: Setup Database

```bash
# Start PostgreSQL (if using Docker)
docker run -d --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  timescale/timescaledb:latest-pg14

# Wait a few seconds, then initialize schema
psql -U postgres -h localhost << EOF
CREATE DATABASE monitor;
\c monitor
\i ops/sql/schema.sql
EOF
```

## Step 3: Configure Services

Create a simple `.env` file:

```bash
cat > .env << EOF
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/monitor

# Services
LOCAL_API_BASE=http://localhost:18000
SIDECAR_URL=http://localhost:8000

# Logging
LOG_LEVEL=INFO
JSON_LOGS=false
EOF
```

## Step 4: Start Services

Open 3 terminals and run:

**Terminal 1 - Local API:**
```bash
cd apps/local_api
export $(cat ../../.env | xargs)
python main.py
```

**Terminal 2 - Sidecar Agent:**
```bash
cd apps/sidecar_agent
export $(cat ../../.env | xargs)
python main.py
```

**Terminal 3 - Web Dashboard:**
```bash
cd apps/web_local
export $(cat ../../.env | xargs)
streamlit run streamlit_app.py
```

## Step 5: Test It!

Run the test script to generate sample data:

```bash
python << 'PYTHON'
from uuid import uuid4
import time
from apps.monitoring_sdk.monitoring_sdk import Monitored, AppRef

app = AppRef(app_id=uuid4(), name='quick-start-demo', version='1.0')

print("Creating test jobs...")
for i in range(5):
    with Monitored(
        site_id='quick-start',
        app=app,
        entity_type='job',
        business_key=f'test-job-{i}'
    ):
        # Simulate work
        time.sleep(0.5)
    print(f"✓ Job {i+1}/5 completed")

print("\n🎉 Success! Check the dashboard at http://localhost:8501")
PYTHON
```

## Step 6: View Your Data

Open your browser to:
- **Dashboard**: http://localhost:8501
- **Local API Health**: http://localhost:18000/v1/healthz
- **Sidecar Health**: http://localhost:8000/v1/healthz
- **Metrics**: http://localhost:18000/metrics

You should see:
- ✅ 5 jobs in the dashboard
- ✅ Performance metrics (CPU, memory, duration)
- ✅ Status charts
- ✅ Timeline visualization

## Next Steps

### Add More Features

1. **Enable Tracing:**
   ```bash
   # Add to .env
   echo "ENABLE_TRACING=true" >> .env
   echo "OTLP_ENDPOINT=http://localhost:4317" >> .env
   
   # Start OpenTelemetry Collector (optional)
   docker run -d --name otel-collector \
     -p 4317:4317 \
     otel/opentelemetry-collector
   ```

2. **Setup Prometheus:**
   ```bash
   # Create prometheus.yml
   cat > prometheus.yml << EOF
   scrape_configs:
     - job_name: 'wafer-monitor'
       static_configs:
         - targets: ['localhost:8000', 'localhost:18000']
   EOF
   
   # Start Prometheus
   docker run -d --name prometheus \
     -p 9090:9090 \
     -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
     prom/prometheus
   ```

3. **Enable Alerts:**
   ```bash
   # Add to .env
   echo "SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK" >> .env
   ```

### Run Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires running services)
pytest tests/integration/ -v

# Performance tests
pytest tests/performance/ -v -s
```

### Deploy to Production

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment guides.

## Common Issues

### "Connection refused" errors

- ✅ Check PostgreSQL is running: `pg_isready -h localhost`
- ✅ Verify services are on correct ports
- ✅ Check firewall settings

### No data in dashboard

- ✅ Verify Local API is receiving data: `curl http://localhost:18000/v1/jobs`
- ✅ Check spool directory: `ls /tmp/sidecar-spool/`
- ✅ Review logs for errors

### Import errors

- ✅ Ensure virtual environment is activated
- ✅ Reinstall dependencies: `pip install -e .`

## Architecture Overview

```
Your App → Sidecar Agent → Local API → TimescaleDB
                 ↓              ↓
              (spool)    Web Dashboard
```

## What's Happening?

1. **Your App** uses the monitoring SDK to track jobs
2. **Sidecar Agent** receives events and forwards to Local API
   - If Local API is down, events are spooled locally
3. **Local API** stores events in TimescaleDB
4. **Web Dashboard** queries the API and displays visualizations

## Learn More

- 📖 [Full README](README.md) - Complete documentation
- 🔌 [API Documentation](docs/API.md) - API reference
- 🚀 [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment
- 📝 [Changelog](CHANGELOG.md) - What's new in v2.0

## Need Help?

- Check logs: All services log to stdout
- View metrics: http://localhost:18000/metrics
- Health checks: http://localhost:8000/v1/healthz

Happy monitoring! 🎉

