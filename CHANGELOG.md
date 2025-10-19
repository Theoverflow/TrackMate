# Changelog

All notable changes to the Wafer Monitor project will be documented in this file.

## [2.0.0] - 2025-10-19

### 🎉 Major Enhancements

#### Observability & Monitoring
- ✨ **Structured Logging**: Integrated `structlog` for JSON-formatted, structured logs across all services
- ✨ **Distributed Tracing**: Added OpenTelemetry support for end-to-end request tracing
- ✨ **Prometheus Metrics**: Comprehensive metrics collection with `/metrics` endpoints on all services
- ✨ **Alert System**: Configurable alerting with Slack, Webhook, and Email notifications

#### Performance & Reliability
- ⚡ **Enhanced Error Handling**: Automatic retries with exponential backoff using `tenacity`
- ⚡ **Connection Pooling**: Optimized database connection management
- ⚡ **Batch Processing**: Improved batch event ingestion with better throughput
- ⚡ **Caching**: Dashboard caching with configurable TTL

#### Developer Experience
- 📚 **Configuration Management**: Pydantic-based configuration with validation
- 📚 **Comprehensive Tests**: Unit, integration, and performance test suites
- 📚 **API Documentation**: Detailed OpenAPI schemas and response models
- 📚 **Enhanced SDK**: Better error messages, logging, and retry logic

#### User Interface
- 🎨 **Real-time Updates**: Auto-refresh capabilities in dashboards
- 🎨 **Interactive Charts**: Plotly-based visualizations with drill-down
- 🎨 **Performance Analytics**: CPU, memory, and duration analysis
- 🎨 **Multi-site Comparison**: Side-by-side site performance comparison

### 📦 New Components

- `apps/shared_utils/` - Shared utilities module
  - `logging.py` - Structured logging setup
  - `tracing.py` - OpenTelemetry configuration
  - `metrics.py` - Prometheus metrics collector
  - `config.py` - Configuration management
  - `alerts.py` - Alert management system

### 🔧 Improvements

#### Sidecar Agent
- Added metrics collection for spool directory size
- Enhanced health check with detailed status
- Improved error logging with context
- Added request/response metrics

#### Local API
- Database operation timing metrics
- Query performance tracking
- Enhanced error messages with details
- Connection pool monitoring
- Configurable query limits

#### Central API
- Site health aggregation
- Request forwarding metrics
- Better error propagation
- Sites listing endpoint

#### Monitoring SDK
- Context manager improvements
- Better exception handling
- Progress tick functionality
- Configurable logging
- Enhanced metadata support

#### Dashboards
- Performance summary statistics
- Application breakdown views
- Export to CSV functionality
- Customizable filters
- Status distribution charts
- Time-series visualizations

### 🐛 Bug Fixes

- Fixed timezone handling in queries
- Improved idempotency key handling
- Corrected memory calculation accuracy
- Fixed connection pool cleanup

### 📖 Documentation

- Complete README with usage examples
- API documentation with request/response schemas
- Deployment guide with multiple deployment options
- Performance tuning guide
- Troubleshooting section

### 🧪 Testing

- Added unit tests for SDK components
- Integration tests for API endpoints
- Performance benchmarks and load tests
- Test fixtures and helpers

### ⚙️ Configuration

- Environment-based configuration
- Validation with Pydantic
- Sensible defaults
- Configuration documentation

### 📊 Metrics Added

- `http_requests_total` - HTTP request counter
- `http_request_duration_seconds` - Request latency
- `db_operations_total` - Database operation counter
- `db_operation_duration_seconds` - DB operation latency
- `db_pool_size` - Connection pool size gauge
- `db_pool_available` - Available connections
- `events_processed_total` - Event processing counter
- `events_in_spool` - Spool directory size
- `jobs_total` - Job counter by status
- `job_duration_seconds` - Job duration histogram

### 🚨 Alert Rules Added

- High failure rate (>10%)
- Long running jobs (>1 hour)
- High memory usage (>8GB)
- No jobs received
- Event ingestion lag
- Database connection failures

### 🔄 Breaking Changes

- Updated Python requirement to 3.10+
- Changed configuration to use Pydantic models
- Updated event schema to include more metadata
- Modified SDK imports (added enable_logging parameter)

### 📝 Dependencies Added

- `structlog>=24.1.0` - Structured logging
- `opentelemetry-api>=1.20.0` - Tracing API
- `opentelemetry-sdk>=1.20.0` - Tracing SDK
- `opentelemetry-instrumentation-fastapi>=0.41b0` - FastAPI instrumentation
- `opentelemetry-exporter-otlp>=1.20.0` - OTLP exporter
- `prometheus-client>=0.19.0` - Metrics collection
- `tenacity>=8.2.0` - Retry logic
- `plotly>=5.18.0` - Interactive charts
- `pydantic-settings>=2.0.0` - Configuration management

## [0.2.0] - Previous Version

### Initial separated environments architecture
- Sidecar agent for event forwarding
- Local API with TimescaleDB
- Central API for multi-site aggregation
- Basic Streamlit dashboards
- S3 archiver
- 72-hour retention with 10-year archival

---

## Migration Guide: 0.2.0 → 2.0.0

### Code Changes

#### SDK Usage

**Before:**
```python
with Monitored(site_id='fab', app=app, entity_type='job', emitter=emitter):
    pass
```

**After:**
```python
# Works the same, but now with optional logging control
with Monitored(
    site_id='fab',
    app=app,
    entity_type='job',
    emitter=emitter,
    enable_logging=True  # New optional parameter
):
    pass
```

#### Configuration

**Before:**
```python
# Environment variables only
LOCAL_API_BASE = os.getenv('LOCAL_API_BASE', 'http://localhost:18000')
```

**After:**
```python
# Pydantic configuration with validation
from shared_utils import SidecarAgentConfig
config = SidecarAgentConfig()  # Loads from env or .env file
```

### Deployment Changes

1. **Update Dependencies:**
   ```bash
   pip install -e . --upgrade
   ```

2. **Add Environment Variables:**
   - `ENABLE_TRACING` (optional)
   - `OTLP_ENDPOINT` (if tracing enabled)
   - Alert webhook URLs (optional)

3. **Update Monitoring:**
   - Configure Prometheus to scrape `/metrics` endpoints
   - Set up OpenTelemetry collector (optional)
   - Configure alert destinations

4. **Database:**
   - No schema changes required
   - Existing data is compatible

### Testing

Run tests to verify migration:
```bash
pytest tests/ -v
```

