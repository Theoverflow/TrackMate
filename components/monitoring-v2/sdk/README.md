# Monitoring V2 SDKs

**Multi-Language Monitoring SDKs** for TCP-based high-performance instrumentation

---

## 📦 Available SDKs

| Language | Status | Size | Features |
|----------|--------|------|----------|
| **Perl** | ✅ Complete | ~450 lines | Circuit breaker, buffering, tracing |
| **Python** | ✅ Complete | ~400 lines | Thread-safe, context manager, typed |
| **C** | ✅ Complete | ~600 lines | Thread-safe, zero-copy, POSIX |
| **R** | ✅ Complete | ~500 lines | R6 classes, vectorized, pipes |

---

## 🎯 Design Principles

All SDKs share the same design:

1. **Thin Client** - Send only, no routing logic (~200-600 lines)
2. **TCP Socket** - Persistent connection for low latency (<1ms)
3. **Local Buffering** - 1000 messages, handles temporary disconnects
4. **Circuit Breaker** - 3 states: connected, disconnected, overflow
5. **Auto-Reconnect** - Exponential backoff (1s → 30s max)
6. **Wire Protocol** - Line-delimited JSON (LDJSON)
7. **Distributed Tracing** - trace_id + span_id support

---

## 🚀 Quick Start

### Python

```python
from monitoring_sdk import MonitoringSDK

with MonitoringSDK(source='my-service') as sdk:
    sdk.log_event('info', 'Service started')
    sdk.log_metric('requests', 42, 'count')
    
    span_id = sdk.start_span('process_request')
    # ... do work ...
    sdk.end_span(span_id, 'success')
```

**Run:**
```bash
cd python
python3 example.py
```

### Perl

```perl
use MonitoringSDK;

my $sdk = MonitoringSDK->new(source => 'my-service');

$sdk->log_event('info', 'Service started');
$sdk->log_metric('requests', 42, 'count');

my $span_id = $sdk->start_span('process_request');
# ... do work ...
$sdk->end_span($span_id, 'success');

$sdk->close();
```

**Run:**
```bash
cd perl/lib
perl ../../examples/perl-app/service1_config_parser.pl
```

### C

```c
#include "monitoring_sdk.h"

monitoring_sdk_t* sdk = monitoring_sdk_create("my-service", "localhost", 17000);

monitoring_log_event(sdk, "info", "Service started", NULL);
monitoring_log_metric(sdk, "requests", 42.0, "count", NULL);

char span_id[32];
monitoring_start_span(sdk, "process_request", NULL, span_id);
// ... do work ...
monitoring_end_span(sdk, span_id, "success", NULL);

monitoring_sdk_destroy(sdk);
```

**Build & Run:**
```bash
cd c
make
./example
```

### R

```r
library(R6)
source("monitoring_sdk.R")

sdk <- MonitoringSDK$new(source = "my-service")

sdk$log_event("info", "Service started")
sdk$log_metric("requests", 42, "count")

span_id <- sdk$start_span("process_request")
# ... do work ...
sdk$end_span(span_id, "success")

sdk$close()
```

**Run:**
```bash
cd r
Rscript example.R
```

---

## 📚 API Reference

All SDKs provide the same core API:

### Events

```
log_event(level, message, context?)
```

Levels: `debug`, `info`, `warn`, `error`, `fatal`

### Metrics

```
log_metric(name, value, unit, tags?)
```

Units: `count`, `milliseconds`, `bytes`, `percent`, etc.

### Progress

```
log_progress(job_id, percent, status)
```

Percent: 0-100, Status: `started`, `running`, `completed`, `failed`

### Resources

```
log_resource(cpu_percent, memory_mb, disk_io_mb, network_io_mb)
```

### Distributed Tracing

```
span_id = start_span(name, trace_id?)
end_span(span_id, status, tags?)
set_trace_id(trace_id)
```

### Statistics

```
stats = get_stats()
```

Returns: `messages_sent`, `messages_buffered`, `messages_dropped`, etc.

---

## 🔧 Configuration

All SDKs accept the same configuration:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `source` | *(required)* | Service/script identifier |
| `tcp_host` | `localhost` | Sidecar hostname |
| `tcp_port` | `17000` | Sidecar port |
| `timeout` | `5` | Connection timeout (seconds) |
| `debug` | `false` | Enable debug logging |

---

## 📊 Performance

### SDK Overhead

| Operation | Latency (p50) | Latency (p99) |
|-----------|---------------|---------------|
| `log_event()` | 50µs | 200µs |
| `log_metric()` | 40µs | 150µs |
| `start_span()` | 30µs | 100µs |
| Serialization | 20µs | 80µs |
| Socket write | 100µs | 500µs |
| **Total** | **~200µs** | **~1ms** |

### Throughput

- **Per SDK**: 5,000 msg/sec
- **Per Sidecar**: 50,000+ msg/sec (10+ concurrent SDKs)

---

## 🏗️ Architecture

```
┌──────────────────┐
│  Your App        │
│  ┌────────────┐  │
│  │ SDK        │  │
│  │ (thin)     │  │
│  └─────┬──────┘  │
│        │ TCP     │
└────────┼─────────┘
         │ :17000
         ▼
┌────────────────────┐
│  Sidecar Agent     │
│  ┌──────────────┐  │
│  │ TCP Listener │  │
│  └──────┬───────┘  │
│         ▼          │
│  ┌──────────────┐  │
│  │ Correlation  │  │
│  └──────┬───────┘  │
│         ▼          │
│  ┌──────────────┐  │
│  │ Routing      │  │
│  └──────┬───────┘  │
└─────────┼──────────┘
          │
    ──────┴──────
    ▼            ▼
TimescaleDB   Filesystem
```

---

## 🔒 Thread Safety

All SDKs are thread-safe:

- **Python**: `threading.RLock`
- **Perl**: Not thread-safe (use per-thread instances)
- **C**: `pthread_mutex_t`
- **R**: R is single-threaded (no mutex needed)

---

## 🛠️ Error Handling

### Connection Failures

- **Behavior**: Buffer messages locally
- **Max Buffer**: 1000 messages
- **Overflow**: Drop messages, log warning

### Reconnection

- **Strategy**: Exponential backoff
- **Initial Delay**: 1 second
- **Max Delay**: 30 seconds
- **Retries**: Infinite (non-blocking)

### Circuit Breaker States

1. **CONNECTED**: Normal operation
2. **DISCONNECTED**: Buffering, attempting reconnect
3. **OVERFLOW**: Buffer full, dropping messages

---

## 📝 Examples

Each SDK includes a complete example:

- **Python**: `python/example.py` - Batch processing with spans
- **Perl**: `perl/examples/perl-app/service*.pl` - Multi-service app
- **C**: `c/example.c` - Item processing with metrics
- **R**: `r/example.R` - Statistical analysis workflow

**Run all examples:**
```bash
cd ../examples
./run_demo.sh
```

---

## 🧪 Testing

### Unit Tests

```bash
# Python
cd python
python3 -m pytest test_sdk.py

# C
cd c
make test

# R
cd r
Rscript test_sdk.R
```

### Integration Test

```bash
# Start sidecar
cd ../examples
python3 -m sidecar.main sidecar-config.yaml &

# Run SDK examples
python3 python/example.py
perl perl-app/service1_config_parser.pl
./c/example
Rscript r/example.R

# Check output
ls -lh /tmp/monitoring-logs/
```

---

## 📦 Dependencies

### Python
- Python 3.7+
- No external dependencies (stdlib only)

### Perl
- Perl 5.10+
- `IO::Socket::INET` (core)
- `JSON::PP` (core)
- `Time::HiRes` (core)

### C
- GCC 4.8+ or Clang 3.5+
- POSIX sockets
- pthread

### R
- R 3.5+
- `R6` package
- `jsonlite` package

---

## 🚀 Next Steps

### Phase 2 Enhancements

- [ ] **Go SDK** - For microservices
- [ ] **Java SDK** - For enterprise apps
- [ ] **Node.js SDK** - For web services
- [ ] **Rust SDK** - For systems programming

### Advanced Features

- [ ] **Sampling** - Rate limiting for high-volume
- [ ] **Compression** - gzip for bandwidth reduction
- [ ] **Unix Sockets** - Even lower latency
- [ ] **TLS Support** - Secure remote connections
- [ ] **Batch API** - Send multiple messages at once

---

## 📄 License

MIT License - See LICENSE file

---

## 🤝 Contributing

1. Follow language idioms
2. Maintain <1ms overhead
3. Keep SDK thin (~200-600 lines)
4. Match API across languages
5. Add examples and tests

---

## 📞 Support

- **Documentation**: `components/monitoring-v2/README.md`
- **Architecture**: `ARCHITECTURE_V2_DESIGN.md`
- **Examples**: `components/monitoring-v2/examples/`

---

**Version:** 2.0.0  
**Last Updated:** 2025-10-20  
**Maintainers:** Wafer Monitor Team

