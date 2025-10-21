# Architecture V2 - Refined Design

**Version:** 2.0.0  
**Date:** 2025-10-20  
**Status:** 🎯 **REFINED - READY FOR IMPLEMENTATION**

---

## 🎯 Design Refinements

### 1. **Protocol Specification**

**Wire Protocol - Line-Delimited JSON (LDJSON)**

Why LDJSON over MessagePack:
- ✅ Human-readable for debugging
- ✅ No library dependencies in simple cases
- ✅ Streaming-friendly
- ✅ Standard format
- ❌ Slightly larger than MessagePack (~20% overhead acceptable)

**Message Format:**
```json
{"v":1,"src":"queue-service","ts":1697821234567,"type":"event","tid":"trace-123","sid":"span-456","data":{"level":"info","msg":"Job started","ctx":{"job_id":"12345"}}}
```

**Field Abbreviations** (reduce size):
- `v` = version
- `src` = source
- `ts` = timestamp (unix millis)
- `type` = message type
- `tid` = trace_id (optional)
- `sid` = span_id (optional)
- `pid` = parent_span_id (optional)
- `data` = payload

**Message Types:**
1. `event` - Log event (level, message, context)
2. `metric` - Metric (name, value, unit, tags)
3. `progress` - Job progress (job_id, percent, status)
4. `resource` - Resource usage (cpu, mem, disk, net)
5. `span` - Distributed trace span
6. `heartbeat` - Keep-alive from SDK

**Frame Format:**
```
<JSON message>\n
<JSON message>\n
<JSON message>\n
```

Each message terminated by `\n` (newline). Max message size: 64KB.

---

### 2. **Error Handling & Resilience**

#### SDK Local Buffer (Circuit Breaker)
```
SDK State Machine:
┌─────────────┐
│   CONNECTED │ ◄─────────┐
└──────┬──────┘            │
       │                   │
       │ socket error      │ reconnect success
       │                   │
       ▼                   │
┌─────────────┐            │
│ DISCONNECTED├────────────┘
└──────┬──────┘
       │
       │ buffer full
       │
       ▼
┌─────────────┐
│  OVERFLOW   │ → drop messages (log warning)
└─────────────┘
```

**SDK Buffering Strategy:**
```perl
# SDK maintains local buffer
my $buffer = [];
my $MAX_BUFFER_SIZE = 1000;  # messages
my $state = 'DISCONNECTED';

sub send_message {
    my ($msg) = @_;
    
    if ($state eq 'CONNECTED') {
        eval {
            $socket->send($msg . "\n");
        };
        if ($@) {
            $state = 'DISCONNECTED';
            push @$buffer, $msg;
            schedule_reconnect();
        }
    } else {
        # Buffer locally
        if (@$buffer < $MAX_BUFFER_SIZE) {
            push @$buffer, $msg;
        } else {
            # Overflow: drop oldest or log warning
            $OVERFLOW_COUNT++;
        }
    }
}

sub reconnect {
    eval {
        $socket = IO::Socket::INET->new(
            PeerAddr => $host,
            PeerPort => $port,
            Proto    => 'tcp',
        );
        $state = 'CONNECTED';
        
        # Flush buffer
        while (my $msg = shift @$buffer) {
            $socket->send($msg . "\n");
        }
    };
    if ($@) {
        schedule_reconnect();  # Exponential backoff
    }
}
```

#### Sidecar Backpressure
```python
class TCPListener:
    def __init__(self, max_queue_size=10000):
        self.queue = asyncio.Queue(maxsize=max_queue_size)
    
    async def handle_connection(self, reader, writer):
        while True:
            try:
                line = await reader.readline()
                
                if self.queue.full():
                    # Backpressure: slow down reading
                    await asyncio.sleep(0.1)
                    # Drop message or apply sampling
                    if should_sample():
                        await self.queue.put(parse(line))
                else:
                    await self.queue.put(parse(line))
                    
            except Exception as e:
                logger.error(f"Connection error: {e}")
                break
```

---

### 3. **Security Considerations**

**Option 1: Localhost Only (Recommended for MVP)**
```yaml
tcp:
  host: "127.0.0.1"  # localhost only
  port: 17000
```

**Option 2: Unix Domain Sockets (Best for single-host)**
```python
# Use Unix socket instead of TCP
socket_path = "/var/run/monitoring/sidecar.sock"
server = await asyncio.start_unix_server(
    handle_connection,
    path=socket_path
)
```

**Option 3: TLS + Authentication (For remote)**
```yaml
tcp:
  host: "0.0.0.0"
  port: 17000
  tls:
    enabled: true
    cert: /etc/monitoring/cert.pem
    key: /etc/monitoring/key.pem
  auth:
    type: shared_secret
    secret: "${MONITORING_SECRET}"
```

**Recommendation:** Start with localhost TCP (Phase 1), add Unix sockets in Phase 2.

---

### 4. **Sidecar Self-Monitoring**

Sidecar exposes metrics about itself:

```python
class SidecarMetrics:
    messages_received = Counter('sidecar_messages_received_total', ['source'])
    messages_routed = Counter('sidecar_messages_routed_total', ['backend'])
    messages_dropped = Counter('sidecar_messages_dropped_total', ['reason'])
    buffer_size = Gauge('sidecar_buffer_size', ['source'])
    backend_latency = Histogram('sidecar_backend_latency_seconds', ['backend'])
    active_connections = Gauge('sidecar_active_connections')
```

**Metrics Endpoint:**
```
GET http://localhost:17001/metrics  (Prometheus format)
GET http://localhost:17001/health   (JSON health status)
```

---

### 5. **Configuration Hot-Reload - Improved**

**File Watcher with Validation:**
```python
class ConfigWatcher:
    def __init__(self, config_path, on_reload):
        self.config_path = config_path
        self.on_reload = on_reload
        self.last_config = None
        self.last_mtime = 0
    
    async def watch(self):
        while True:
            try:
                mtime = os.path.getmtime(self.config_path)
                
                if mtime > self.last_mtime:
                    # Config changed
                    new_config = self.load_and_validate(self.config_path)
                    
                    if new_config:
                        # Validate before applying
                        if self.validate_config(new_config):
                            await self.on_reload(new_config)
                            self.last_config = new_config
                            self.last_mtime = mtime
                            logger.info("✓ Config reloaded successfully")
                        else:
                            logger.error("✗ Invalid config, keeping old config")
                    else:
                        logger.error("✗ Failed to parse config")
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Config watch error: {e}")
                await asyncio.sleep(5)
    
    def validate_config(self, config):
        # Validate structure
        if 'routing' not in config:
            return False
        if 'backends' not in config:
            return False
        
        # Validate backend references
        for source, rules in config['routing'].items():
            for rule in rules:
                backend_name = rule['backend']
                if backend_name not in config['backends']:
                    logger.error(f"Unknown backend: {backend_name}")
                    return False
        
        return True
```

---

### 6. **Resource Limits & Tuning**

**Sidecar Configuration:**
```yaml
sidecar:
  tcp:
    host: "127.0.0.1"
    port: 17000
    max_connections: 100
    read_timeout: 30
    keepalive: true
  
  buffers:
    max_queue_size: 10000        # messages
    per_source_buffer: 1000      # messages per source
    flush_interval: 5            # seconds
    flush_batch_size: 100        # messages
  
  performance:
    worker_threads: 4            # for CPU-bound tasks
    max_memory_mb: 512           # memory limit
    gc_interval: 60              # garbage collection
  
  health:
    metrics_port: 17001
    health_check_interval: 10
```

---

### 7. **Graceful Shutdown**

**SDK Shutdown:**
```perl
sub close {
    my ($self) = @_;
    
    # Flush buffer
    $self->flush_buffer();
    
    # Send goodbye message
    $self->send_message({
        type => 'goodbye',
        src => $self->{source}
    });
    
    # Close socket
    $self->{socket}->close() if $self->{socket};
    
    $self->{state} = 'CLOSED';
}

# Register signal handler
$SIG{INT} = $SIG{TERM} = sub {
    $monitoring->close();
    exit(0);
};
```

**Sidecar Shutdown:**
```python
class Sidecar:
    async def shutdown(self):
        logger.info("Shutting down gracefully...")
        
        # Stop accepting new connections
        self.listener.close()
        await self.listener.wait_closed()
        
        # Flush all buffers
        await self.correlation_engine.flush_all()
        
        # Wait for in-flight backend operations
        await asyncio.gather(*self.pending_tasks)
        
        # Close backend connections
        for backend in self.backends.values():
            await backend.close()
        
        logger.info("Shutdown complete")

# Signal handler
async def main():
    sidecar = Sidecar()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(sidecar.shutdown())
        )
    
    await sidecar.run()
```

---

### 8. **Trace Correlation - Enhanced**

**Distributed Tracing:**
```
Service 1 (config-service):
  trace_id: abc123
  span_id: span-1
  parent_span_id: null
  duration: 100ms

Service 2 (file-receiver):
  trace_id: abc123
  span_id: span-2
  parent_span_id: span-1
  duration: 50ms

Service 3 (queue-service):
  trace_id: abc123
  span_id: span-3
  parent_span_id: span-2
  duration: 200ms

Script (db-loader):
  trace_id: abc123
  span_id: span-4
  parent_span_id: span-3
  duration: 1500ms
```

**Correlation Engine:**
```python
class TraceCorrelator:
    def __init__(self):
        self.traces = {}  # trace_id -> [spans]
        self.ttl = 3600   # 1 hour
    
    def add_span(self, message):
        trace_id = message.get('tid')
        if not trace_id:
            return
        
        if trace_id not in self.traces:
            self.traces[trace_id] = []
        
        self.traces[trace_id].append({
            'span_id': message['sid'],
            'parent_span_id': message.get('pid'),
            'source': message['src'],
            'timestamp': message['ts'],
            'data': message['data']
        })
    
    def get_trace(self, trace_id):
        spans = self.traces.get(trace_id, [])
        
        # Build trace tree
        return self.build_trace_tree(spans)
    
    def build_trace_tree(self, spans):
        # Create parent-child relationships
        tree = {}
        for span in spans:
            tree[span['span_id']] = span
            span['children'] = []
        
        for span in spans:
            parent_id = span.get('parent_span_id')
            if parent_id and parent_id in tree:
                tree[parent_id]['children'].append(span)
        
        # Find root spans
        roots = [s for s in spans if not s.get('parent_span_id')]
        return roots
```

---

### 9. **Deployment Architecture**

**Option A: Container Sidecar (Recommended)**
```yaml
# docker-compose.yml
services:
  app:
    image: myapp:latest
    depends_on:
      - monitoring-sidecar
    environment:
      - MONITORING_TCP_HOST=monitoring-sidecar
      - MONITORING_TCP_PORT=17000
  
  monitoring-sidecar:
    image: wafermonitor/sidecar:latest
    ports:
      - "17000:17000"  # TCP listener
      - "17001:17001"  # Metrics/health
    volumes:
      - ./sidecar-config.yaml:/etc/monitoring/config.yaml:ro
      - /mnt/nas/logs:/mnt/nas/logs
    environment:
      - CONFIG_FILE=/etc/monitoring/config.yaml
```

**Option B: Systemd Service (Bare Metal)**
```ini
# /etc/systemd/system/monitoring-sidecar.service
[Unit]
Description=Monitoring Sidecar Agent
After=network.target

[Service]
Type=simple
User=monitoring
ExecStart=/usr/local/bin/monitoring-sidecar --config /etc/monitoring/config.yaml
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

---

### 10. **Performance Benchmarks (Expected)**

**SDK Overhead:**
```
Operation                    Latency (p50)    Latency (p99)
─────────────────────────────────────────────────────────
log_event()                  50µs             200µs
log_metric()                 40µs             150µs
start_span()                 30µs             100µs
Serialization (JSON)         20µs             80µs
Socket write                 100µs            500µs
─────────────────────────────────────────────────────────
Total per call               ~200µs           ~1ms
```

**Sidecar Throughput:**
```
Metric                       Target           Notes
─────────────────────────────────────────────────────────
Messages/sec (single core)   50,000+          Async I/O
Messages/sec (4 cores)       150,000+         Parallel processing
Latency (receive → route)    <5ms (p50)       Buffering adds 0-5s
Memory per 1K msg buffer     ~500KB           JSON in memory
CPU (idle)                   <1%              Event-driven
CPU (50K msg/s)              ~30%             4 cores
─────────────────────────────────────────────────────────
```

---

## 📊 Comparison: Old vs New Architecture

| Aspect | Old (HTTP-based) | New (TCP-based) |
|--------|------------------|-----------------|
| **SDK Size** | 1000+ lines | ~200 lines |
| **Protocol Overhead** | HTTP headers (~500 bytes) | Line delimiter (1 byte) |
| **Connection** | Per-request | Persistent |
| **Latency** | 5-50ms | <1ms |
| **SDK Logic** | Routing, retries, backends | Send only |
| **Throughput** | 1,000 msg/s | 50,000+ msg/s |
| **Maintenance** | 5 SDKs to update | Update sidecar only |

---

## ✅ Refined Design Summary

### **Key Improvements:**
1. ✅ **Line-delimited JSON protocol** (streaming, debuggable)
2. ✅ **SDK local buffering** with circuit breaker
3. ✅ **Sidecar backpressure handling** (queue limits)
4. ✅ **Config validation** before applying
5. ✅ **Self-monitoring** (Prometheus metrics)
6. ✅ **Graceful shutdown** (both SDK and sidecar)
7. ✅ **Trace correlation** with tree building
8. ✅ **Resource limits** and tuning
9. ✅ **Multiple deployment options** (container, systemd)
10. ✅ **Performance benchmarks** defined

---

## 🚀 Implementation Order

### **Phase 1: Core (Week 1) - MVP**
1. Wire protocol definition
2. TCP socket listener (Python asyncio)
3. Basic message parsing
4. Perl SDK (thin client)
5. Simple routing (single backend)
6. Config file loading

### **Phase 2: Reliability (Week 2)**
7. SDK buffering + reconnection
8. Sidecar backpressure
9. Multiple backend support
10. Config hot-reload
11. Graceful shutdown

### **Phase 3: Observability (Week 3)**
12. Trace correlation
13. Sidecar metrics (Prometheus)
14. Health check endpoint
15. Logging framework

### **Phase 4: Scale (Week 4)**
16. Performance tuning
17. Multi-language SDKs (Python, C, R, Java)
18. Load testing
19. Production deployment

---

**Status:** ✅ Design refined and ready for implementation

**Next:** Implement Phase 1 - Core MVP

