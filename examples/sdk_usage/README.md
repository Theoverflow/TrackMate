# SDK Usage Examples

This directory contains examples demonstrating the enhanced monitoring SDK with multi-backend support.

## 📋 Examples

### Example 1: Sidecar Mode
**File**: `example1_sidecar_mode.py`

Demonstrates traditional sidecar routing where events go through the sidecar agent.

**Flow**: SDK → Sidecar Agent → Configured Backends

```bash
# Run example
python example1_sidecar_mode.py
```

**Prerequisites**:
- Sidecar agent running on `http://localhost:17000`

### Example 2: Direct Mode
**Files**: `example2_direct_mode.py` + `example2_direct_mode.yaml`

Demonstrates direct backend routing, bypassing the sidecar.

**Flow**: SDK → Backends (FileSystem + S3 + ELK)

```bash
# Run example
python example2_direct_mode.py
```

**Prerequisites**:
- None (FileSystem backend works without external services)
- Optional: S3 bucket and Elasticsearch for full functionality

## 🎯 Key Concepts

### Mode Selection

**Sidecar Mode**:
- Events sent to sidecar agent via HTTP
- Sidecar routes to backends
- Centralized control
- Better for managed environments

**Direct Mode**:
- Events sent directly to backends
- SDK handles routing
- Better for edge/disconnected scenarios
- More control in application

### Backend Types

| Backend | Use Case | Sidecar | Direct |
|---------|----------|---------|--------|
| **Sidecar** | Forward to agent | N/A | ✅ |
| **FileSystem** | Local backup | ✅ | ✅ |
| **S3** | Long-term archival | ✅ | ✅ |
| **ELK** | Search & analytics | ✅ | ✅ |
| **Zabbix** | Enterprise monitoring | ✅ | ✅ |
| **CloudWatch** | AWS monitoring | ✅ | ✅ |

### Configuration Sources

The SDK supports multiple configuration sources with precedence:

1. **Programmatic** (highest priority)
   ```python
   configure(mode="direct", app_name="my-app")
   ```

2. **Environment Variables**
   ```bash
   export MONITORING_MODE=sidecar
   export MONITORING_APP_NAME=my-app
   ```

3. **Configuration File**
   ```python
   configure("/path/to/config.yaml")
   ```

4. **Defaults** (lowest priority)

## 📝 Example Configuration Files

### Sidecar Mode
```yaml
sdk:
  mode: sidecar
  sidecar:
    url: http://localhost:17000
    timeout: 5.0
    retries: 3
  app:
    name: my-app
    version: 1.0.0
    site_id: fab1
```

### Direct Mode with Multiple Backends
```yaml
sdk:
  mode: direct
  direct_backends:
    - type: filesystem
      enabled: true
      priority: 1
      config:
        path: /data/monitoring
        format: jsonl
    
    - type: s3
      enabled: true
      priority: 2
      config:
        bucket: monitoring-events
        region: us-east-1
    
    - type: elk
      enabled: true
      priority: 3
      config:
        url: http://elasticsearch:9200
        index: monitoring
  
  app:
    name: my-app
    version: 1.0.0
    site_id: fab1
```

## 🚀 Quick Start

### 1. Install SDK
```bash
cd components/monitoring/sdk/python
pip install -e .
```

### 2. Choose Your Mode

#### Sidecar Mode (Recommended for Production)
```python
from monitoring_sdk import configure, Monitored

# Configure
configure(mode="sidecar", app_name="my-app")

# Use
with Monitored("process-wafer") as ctx:
    # Your code here
    ctx.report_progress({"progress": 50})
```

#### Direct Mode (For Edge/Offline)
```python
from monitoring_sdk import configure, BackendRouter, get_config

# Configure from file
configure("/path/to/config.yaml")

# Create router
with BackendRouter(get_config()) as router:
    # Send events
    results = router.send_event(event)
```

## 🔧 Advanced Usage

### Custom Backend Configuration

```python
from monitoring_sdk import (
    configure,
    MonitoringConfig,
    SDKMode,
    BackendConfig,
    BackendType,
    AppConfig
)

config = MonitoringConfig(
    mode=SDKMode.DIRECT,
    direct_backends=[
        BackendConfig(
            type=BackendType.FILESYSTEM,
            enabled=True,
            priority=1,
            config={
                "path": "/custom/path",
                "format": "jsonl"
            }
        ),
        BackendConfig(
            type=BackendType.S3,
            enabled=True,
            priority=2,
            config={
                "bucket": "my-bucket",
                "region": "us-west-2"
            }
        )
    ],
    app=AppConfig(
        name="advanced-app",
        version="2.0.0",
        site_id="fab2"
    )
)

configure(config)
```

### Health Checking

```python
from monitoring_sdk import BackendRouter, get_config

router = BackendRouter(get_config())
health = router.health_check()

for backend_name, is_healthy in health.items():
    print(f"{backend_name}: {'✅' if is_healthy else '❌'}")
```

### Batch Operations

```python
events = [event1, event2, event3]
results = router.send_batch(events)
```

## 📚 More Examples

See the `examples/` directory for more examples:
- Business application integration
- Multi-language examples (C, Java, Perl, R)
- AWS integration examples
- Custom backend implementations

## 🐛 Troubleshooting

### "No backends configured"
- Check your configuration file
- Ensure backends are enabled
- Verify backend configurations are valid

### "Backend connection failed"
- Check network connectivity
- Verify backend URLs/endpoints
- Check credentials (S3, ELK, etc.)

### "All backends failed"
- Check backend health
- Review logs for errors
- Ensure at least one backend is healthy

## 📖 Documentation

- [Configuration Guide](../../docs/SDK_CONFIGURATION.md)
- [Backend Reference](../../docs/BACKEND_REFERENCE.md)
- [Architecture Design](../../ENHANCED_ARCHITECTURE_DESIGN.md)

---

**Questions?** Check the main README or open an issue.

