# Architecture V2 - High-Performance Unified Monitoring System

**Version:** 2.0.0  
**Date:** 2025-10-20  
**Status:** 🎯 **DESIGN PHASE**

---

## 🎯 Vision

**Lightweight multi-language instrumentation** sending data via **TCP sockets** to an **intelligent sidecar** that aggregates, correlates, and routes to multiple configurable targets **without restart**.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BUSINESS APPLICATION                             │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Service 1    │  │ Service 2    │  │ Service 3    │  │ Script    │ │
│  │ (Perl)       │  │ (Perl)       │  │ (Perl)       │  │ (Perl)    │ │
│  │              │  │              │  │              │  │           │ │
│  │ Config Parser│  │ File Receiver│  │ Queue Manager│  │ DB Loader │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                  │                  │                 │       │
│         │ SDK              │ SDK              │ SDK             │ SDK   │
│         │ (thin)           │ (thin)           │ (thin)          │(thin) │
│         │                  │                  │                 │       │
│         └──────────────────┴──────────────────┴─────────────────┘       │
│                                    │                                    │
│                                    │ TCP Socket (high-speed)            │
│                                    │ (localhost:17000)                  │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
                                     ▼
         ┌───────────────────────────────────────────────────────────────┐
         │                     SIDECAR AGENT                             │
         │                   (Container/Daemon)                          │
         │                                                               │
         │  ┌─────────────────────────────────────────────────────────┐ │
         │  │              TCP SOCKET LISTENER                        │ │
         │  │          (Async, Multi-threaded receiver)               │ │
         │  └───────────────────────┬─────────────────────────────────┘ │
         │                          │                                    │
         │                          ▼                                    │
         │  ┌─────────────────────────────────────────────────────────┐ │
         │  │          DATA CORRELATION ENGINE                        │ │
         │  │  • Source identification (service/script name)          │ │
         │  │  • Stream aggregation                                   │ │
         │  │  • Context correlation (trace IDs, job IDs)             │ │
         │  │  • Buffering & batching                                 │ │
         │  └───────────────────────┬─────────────────────────────────┘ │
         │                          │                                    │
         │                          ▼                                    │
         │  ┌─────────────────────────────────────────────────────────┐ │
         │  │         ROUTING ENGINE (Runtime Configurable)           │ │
         │  │                                                         │ │
         │  │  Rules:                                                 │ │
         │  │  • Service-level granularity (per service/script)       │ │
         │  │  │  queue-service → TimescaleDB + NFS                  │ │
         │  │  │  config-service → S3 only                           │ │
         │  │  │                                                      │ │
         │  │  • Global rules (all sources)                           │ │
         │  │    all → CloudWatch                                     │ │
         │  │                                                         │ │
         │  │  Hot-reload: Update routes without restart             │ │
         │  └───────────────────────┬─────────────────────────────────┘ │
         │                          │                                    │
         │                          ▼                                    │
         │  ┌─────────────────────────────────────────────────────────┐ │
         │  │              BACKEND ADAPTERS                           │ │
         │  │  (Async, concurrent delivery)                           │ │
         │  └───────────┬─────────────────────────────────────────────┘ │
         │              │                                                │
         └──────────────┼────────────────────────────────────────────────┘
                        │
        ────────────────┴─────────────────────────────
        │               │                │            │
        ▼               ▼                ▼            ▼
   ┌─────────┐    ┌─────────┐     ┌─────────┐  ┌─────────┐
   │TimeScale│    │   NFS   │     │   S3    │  │CloudWatch│
   │   DB    │    │  File   │     │  Bucket │  │          │
   └─────────┘    └─────────┘     └─────────┘  └─────────┘
```

---

## 📦 Component Architecture

### 1. **SDK (Multi-Language Instrumentation)**

**Purpose:** Lightweight instrumentation library

**Responsibilities:**
- Capture events, metrics, resource usage, business progress
- Serialize data (MessagePack or JSON)
- Send via TCP socket to sidecar
- **NO routing logic**
- **NO backend knowledge**
- **NO HTTP overhead**

**API Surface (All Languages):**
```
init(source_name, tcp_host, tcp_port)
log_event(level, message, context)
log_metric(name, value, unit, tags)
log_progress(job_id, percent, status)
log_resource(cpu, memory, disk, network)
start_span(name) -> span_id
end_span(span_id, status)
set_context(key, value)
close()
```

**Wire Protocol:**
```json
{
  "source": "queue-service",
  "timestamp": "2025-10-20T10:30:45.123Z",
  "type": "metric|event|progress|resource|span",
  "trace_id": "optional-trace-id",
  "span_id": "optional-span-id",
  "data": {
    // type-specific data
  }
}
```

**Size:** ~200-300 lines per language (thin!)

---

### 2. **Sidecar Agent (Intelligent Hub)**

**Purpose:** Aggregation, correlation, and routing

#### 2.1 **TCP Socket Listener**

```python
class TCPSocketListener:
    """
    High-performance async TCP listener
    """
    async def start(self, host, port):
        # Listen on TCP socket
        # Accept multiple connections
        # Each connection = one source (service/script)
        # Non-blocking async I/O
        pass
    
    async def handle_connection(self, reader, writer):
        # Read messages (line-delimited JSON or MessagePack)
        # Parse and validate
        # Pass to correlation engine
        pass
```

**Features:**
- Async I/O (asyncio in Python, tokio in Rust)
- Multiple concurrent connections
- Connection pooling
- Backpressure handling
- Reconnection support

#### 2.2 **Data Correlation Engine**

```python
class CorrelationEngine:
    """
    Correlates data from multiple sources
    """
    def process_message(self, message):
        # Extract source name
        source = message['source']
        
        # Trace correlation
        if trace_id := message.get('trace_id'):
            self.trace_store.add(trace_id, message)
        
        # Buffer for batching
        self.buffers[source].append(message)
        
        # Flush when batch size or time threshold reached
        if should_flush(source):
            self.flush(source)
    
    def flush(self, source):
        # Get messages for source
        messages = self.buffers[source]
        
        # Pass to routing engine
        self.router.route(source, messages)
```

**Features:**
- Trace ID correlation
- Per-source buffering
- Batch optimization
- Context enrichment
- Timestamp normalization

#### 2.3 **Routing Engine (Runtime Configurable)**

```python
class RoutingEngine:
    """
    Routes messages to backends based on rules
    """
    def __init__(self, config_file):
        self.rules = load_rules(config_file)
        self.backends = initialize_backends(self.rules)
        self.watcher = FileWatcher(config_file, self.reload)
    
    def route(self, source, messages):
        # Get routing rules for source
        rules = self.rules.get(source, self.rules['default'])
        
        # Route to each configured backend
        for rule in rules:
            backend = self.backends[rule['backend']]
            
            # Filter messages if needed
            filtered = self.filter(messages, rule.get('filter'))
            
            # Send async
            asyncio.create_task(backend.send(filtered))
    
    async def reload(self):
        # Hot-reload configuration
        new_rules = load_rules(self.config_file)
        self.rules = new_rules
        self.backends = initialize_backends(new_rules)
        logger.info("Configuration reloaded")
```

**Configuration Example:**
```yaml
# sidecar-config.yaml

tcp:
  host: "0.0.0.0"
  port: 17000
  
routing:
  # Service-specific rules
  queue-service:
    - backend: timescaledb
      enabled: true
      priority: 1
      filter:
        types: [metric, event]
    
    - backend: nfs-file
      enabled: true
      priority: 2
      filter:
        types: [event]
      config:
        path: /mnt/nas/logs/queue-service.jsonl
  
  config-service:
    - backend: s3
      enabled: true
      config:
        bucket: monitoring-logs
        prefix: config-service/
  
  # Global rules (applied to all sources)
  default:
    - backend: cloudwatch
      enabled: true
      config:
        log_group: /app/monitoring
        log_stream: "{source}"

backends:
  timescaledb:
    type: postgres
    connection_string: "postgresql://user:pass@localhost:5432/monitoring"
    table: monitoring_events
  
  nfs-file:
    type: filesystem
    base_path: /mnt/nas/logs
  
  s3:
    type: s3
    region: us-east-1
  
  cloudwatch:
    type: cloudwatch
    region: us-east-1
```

#### 2.4 **Backend Adapters**

```python
class BaseBackend:
    async def send(self, messages):
        raise NotImplementedError

class TimescaleDBBackend(BaseBackend):
    async def send(self, messages):
        # Batch insert into TimescaleDB
        async with self.pool.acquire() as conn:
            await conn.executemany(INSERT_QUERY, messages)

class FileSystemBackend(BaseBackend):
    async def send(self, messages):
        # Append to file (JSONL format)
        async with aiofiles.open(self.path, 'a') as f:
            for msg in messages:
                await f.write(json.dumps(msg) + '\n')

class S3Backend(BaseBackend):
    async def send(self, messages):
        # Upload batch to S3
        key = f"{self.prefix}/{timestamp}.jsonl"
        await self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body='\n'.join(json.dumps(m) for m in messages)
        )

class CloudWatchBackend(BaseBackend):
    async def send(self, messages):
        # Send to CloudWatch Logs
        await self.cw_client.put_log_events(
            logGroupName=self.log_group,
            logStreamName=self.log_stream,
            logEvents=[
                {
                    'timestamp': m['timestamp'],
                    'message': json.dumps(m)
                }
                for m in messages
            ]
        )
```

---

## 🔥 Performance Optimizations

### 1. **TCP Socket Communication**
- **Why TCP:** Lower overhead than HTTP, persistent connections
- **Line-delimited JSON:** Fast parsing, streaming support
- **Optional MessagePack:** Binary format for even faster serialization

### 2. **Async I/O**
- Python: `asyncio` with `uvloop` (2-4x faster)
- Rust: `tokio` for extreme performance
- Non-blocking operations throughout

### 3. **Batching**
- Buffer messages per source
- Flush on:
  - Size threshold (e.g., 100 messages)
  - Time threshold (e.g., 5 seconds)
  - Critical event (immediate flush)

### 4. **Connection Pooling**
- Database connections pooled
- Reuse HTTP clients
- Keep-alive for S3/CloudWatch

### 5. **Parallel Routing**
- Route to multiple backends concurrently
- Don't wait for slow backends
- Circuit breaker for failing backends

---

## 💡 Use Case Example

### **Perl Application: 3 Services + 1 Script**

#### Service 1: Config Parser (config-service)
```perl
use Monitoring::SDK;

my $mon = Monitoring::SDK->new(
    source => 'config-service',
    tcp_host => 'localhost',
    tcp_port => 17000
);

$mon->log_event('info', 'Reading config file', {file => $config_file});
my $config = parse_config($config_file);
$mon->log_metric('config_size_kb', length($config) / 1024, 'kilobytes');
$mon->log_event('info', 'Config loaded successfully');
```

**Sidecar routes to:** S3 only (config is backed up)

#### Service 2: File Receiver (file-receiver)
```perl
my $mon = Monitoring::SDK->new(
    source => 'file-receiver',
    tcp_host => 'localhost',
    tcp_port => 17000
);

my $job_id = generate_job_id();
$mon->set_context('job_id', $job_id);
$mon->log_event('info', 'Received file', {filename => $file});

if (validate_file($file, $config)) {
    $mon->log_metric('file_valid', 1);
    enqueue($file);
    $mon->log_event('info', 'File queued');
} else {
    $mon->log_metric('file_valid', 0);
    $mon->log_event('error', 'Invalid file');
}
```

**Sidecar routes to:** TimescaleDB + CloudWatch (important metrics)

#### Service 3: Queue Manager (queue-service)
```perl
my $mon = Monitoring::SDK->new(
    source => 'queue-service',
    tcp_host => 'localhost',
    tcp_port => 17000
);

while (my $job = dequeue()) {
    my $span_id = $mon->start_span('process_job');
    $mon->set_context('job_id', $job->{id});
    
    $mon->log_progress($job->{id}, 0, 'started');
    
    # Call script
    system("perl db_loader.pl $job->{file}");
    
    $mon->log_progress($job->{id}, 100, 'completed');
    $mon->end_span($span_id, 'success');
    
    $mon->log_metric('jobs_processed', 1, 'count');
}
```

**Sidecar routes to:** TimescaleDB + NFS file (metrics + audit log)

#### Script: DB Loader (db-loader)
```perl
my $mon = Monitoring::SDK->new(
    source => 'db-loader',
    tcp_host => 'localhost',
    tcp_port => 17000
);

my $span_id = $mon->start_span('load_data');
$mon->log_event('info', 'Starting DB load', {file => $ARGV[0]});

my $rows = load_file_to_db($ARGV[0]);

$mon->log_metric('rows_loaded', $rows, 'count');
$mon->log_resource(cpu_percent(), memory_mb(), disk_io_mb());
$mon->end_span($span_id, 'success');
```

**Sidecar routes to:** TimescaleDB (DB performance tracking)

### **Unified View**

All services send to same sidecar → Correlation by `job_id` → Single trace:
```
job-12345:
  ├─ file-receiver: File received, validated, queued (2.3s)
  ├─ queue-service: Job dequeued, processing started (0.1s)
  └─ db-loader: Data loaded, 10,000 rows inserted (45.2s)
  
  Total: 47.6s
```

---

## 🔄 Runtime Configuration Changes

**Scenario:** Need to add CloudWatch for debugging

**Without Restart:**
1. Edit `sidecar-config.yaml`:
   ```yaml
   routing:
     queue-service:
       - backend: timescaledb
         enabled: true
       - backend: nfs-file
         enabled: true
       - backend: cloudwatch  # ← NEW
         enabled: true
         config:
           log_group: /debug/queue-service
   ```

2. Save file

3. Sidecar detects change (file watcher)

4. Reloads config

5. **New data flows to CloudWatch immediately**

6. **No service restart, no downtime, no code change**

---

## 📊 Performance Characteristics

### **SDK Overhead**
- Serialization: <0.1ms per message
- Socket write: <0.5ms per message
- Total: <1ms per instrumentation call

### **Sidecar Throughput**
- TCP: 100,000+ messages/sec (single instance)
- Batching: 10x improvement in backend writes
- Async routing: No blocking on slow backends

### **Latency**
- End-to-end (instrument → backend): <10ms (p50)
- Buffering adds: 0-5 seconds (configurable)
- Critical events: <1ms (immediate flush)

---

## 🎯 Key Benefits

### **1. Performance**
- ✅ TCP faster than HTTP
- ✅ Async I/O throughout
- ✅ Batching reduces backend load
- ✅ No blocking operations

### **2. Maintainability**
- ✅ Simple SDKs (200 lines each)
- ✅ All logic in sidecar (single codebase)
- ✅ Easy to add new backends
- ✅ Clear separation of concerns

### **3. Flexibility**
- ✅ Runtime config changes
- ✅ Per-service routing
- ✅ Global rules
- ✅ Easy to add new sources

### **4. Operational**
- ✅ No service restarts for config changes
- ✅ Sidecar can be updated independently
- ✅ Circuit breakers for resilience
- ✅ Graceful degradation

### **5. Observability**
- ✅ Unified view across services
- ✅ Trace correlation
- ✅ Service-level granularity
- ✅ Rich context

---

## 🚀 Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
- [ ] TCP Socket Listener (async)
- [ ] Message protocol definition
- [ ] Basic SDK (Perl)
- [ ] Correlation engine
- [ ] Configuration loader

### Phase 2: Routing & Backends (Week 2)
- [ ] Routing engine
- [ ] Runtime config reload
- [ ] TimescaleDB backend
- [ ] Filesystem backend
- [ ] S3 backend

### Phase 3: Multi-Language SDKs (Week 3)
- [ ] Python SDK
- [ ] C SDK
- [ ] R SDK
- [ ] Java SDK
- [ ] Protocol tests

### Phase 4: Advanced Features (Week 4)
- [ ] CloudWatch backend
- [ ] Trace correlation UI
- [ ] Metrics aggregation
- [ ] Performance optimization
- [ ] Production testing

---

**Next:** Implement Phase 1 - Core Infrastructure

