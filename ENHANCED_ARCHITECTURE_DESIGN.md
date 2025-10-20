# Enhanced Architecture Design Document

## 🎯 Executive Summary

This document details the enhanced architecture for the Wafer Monitor / TrackMate system with:
- **Multi-language SDK support** (Python, C, R, Perl, Java)
- **Flexible routing** (sidecar vs direct-to-backend)
- **Pluggable backends** (FS, S3, ELK, Zabbix, AWS, Queues, DBs)
- **Dual API endpoints** (managed + external)
- **Unified data access** for Web UI

---

## 🏗️ New Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      BUSINESS APPLICATION LAYER                      │
│                                                                       │
│    ┌────────────────────────────────────────────────────────────┐   │
│    │         Multi-Language Applications                        │   │
│    │   Python │ Java │ C │ R │ Perl │ ...                       │   │
│    └────────────────┬───────────────────────────────────────────┘   │
│                     │                                                │
│    ┌────────────────▼───────────────────────────────────────────┐   │
│    │         Universal Monitoring SDK                           │   │
│    │   - Python SDK                                             │   │
│    │   - C SDK (libmonitoring.so)                               │   │
│    │   - R SDK (monitoring package)                             │   │
│    │   - Perl SDK (Monitoring:: module)                         │   │
│    │   - Java SDK (monitoring-sdk.jar)                          │   │
│    └────────────────┬───────────────────────────────────────────┘   │
│                     │                                                │
└─────────────────────┼────────────────────────────────────────────────┘
                      │
         ┌────────────▼──────────┐
         │   Configuration       │
         │   mode: sidecar/direct│
         │   backends: [...]     │
         └────────────┬──────────┘
                      │
          ┌───────────┴────────────┐
          │                        │
  ┌───────▼────────┐      ┌───────▼───────────────┐
  │ Mode: Sidecar  │      │  Mode: Direct         │
  └───────┬────────┘      └───────┬───────────────┘
          │                       │
          │                       ↓
          │           ┌───────────────────────────┐
          │           │   Direct Backends         │
          │           │   ├─ File System          │
          │           │   ├─ S3                   │
          │           │   ├─ ELK/Loki             │
          │           │   ├─ Zabbix               │
          │           │   ├─ AWS CloudWatch       │
          │           │   ├─ Kafka/SQS            │
          │           │   └─ Custom Webhooks      │
          │           └───────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         SIDECAR LAYER                                │
│                                                                       │
│    ┌──────────────────────────────────────────────────────────┐     │
│    │              Sidecar Agent (Enhanced)                    │     │
│    │                                                          │     │
│    │   HTTP Server :17000                                    │     │
│    │   └─ POST /v1/ingest/events                             │     │
│    │   └─ GET /health                                        │     │
│    │                                                          │     │
│    │   ┌────────────────────────────────────────────────┐    │     │
│    │   │         Backend Router                         │    │     │
│    │   │  (Pluggable, Priority-based, Concurrent)       │    │     │
│    │   └───────┬────────────────────────────────────────┘    │     │
│    │           │                                             │     │
│    │           ├──> Managed API Backend                      │     │
│    │           ├──> File System Backend                      │     │
│    │           ├──> S3 Backend                               │     │
│    │           ├──> ELK Backend                              │     │
│    │           ├──> Zabbix Backend                           │     │
│    │           ├──> CloudWatch Backend                       │     │
│    │           ├──> Queue Backend (Kafka/SQS/RabbitMQ)       │     │
│    │           └──> External DB Backend (MySQL/Mongo/...)    │     │
│    │                                                          │     │
│    │   ┌────────────────────────────────────────────────┐    │     │
│    │   │         Spool Manager (Resilience)            │    │     │
│    │   │  - Local disk buffer                          │    │     │
│    │   │  - Retry failed events                        │    │     │
│    │   │  - Backpressure handling                      │    │     │
│    │   └────────────────────────────────────────────────┘    │     │
│    └──────────────────────────────────────────────────────────┘     │
│                                                                       │
└───────────────────────────┬───────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     DATA PLANE LAYER (Enhanced)                      │
│                                                                       │
│    ┌──────────────────────────────────────────────────────────┐     │
│    │            API Gateway (Dual Endpoint)                   │     │
│    │                                                          │     │
│    │   ┌──────────────────────────────────────────────┐      │     │
│    │   │  POST /v1/ingest/managed                     │      │     │
│    │   │   - Receive events from SDK/Sidecar          │      │     │
│    │   │   - Write to TimescaleDB                     │      │     │
│    │   │   - Batch processing                         │      │     │
│    │   │   - Schema validation                        │      │     │
│    │   └──────────────────────────────────────────────┘      │     │
│    │                                                          │     │
│    │   ┌──────────────────────────────────────────────┐      │     │
│    │   │  POST /v1/query/external                     │      │     │
│    │   │   - Query external data sources              │      │     │
│    │   │   - S3 Reader (Parquet/JSON)                 │      │     │
│    │   │   - ELK Reader (Elasticsearch Query)         │      │     │
│    │   │   - Zabbix Reader (Zabbix API)               │      │     │
│    │   │   - CloudWatch Reader (CloudWatch Insights)  │      │     │
│    │   │   - Custom Adapter Framework                 │      │     │
│    │   └──────────────────────────────────────────────┘      │     │
│    │                                                          │     │
│    │   ┌──────────────────────────────────────────────┐      │     │
│    │   │  GET /v1/data/unified                        │      │     │
│    │   │   - Merge managed + external data            │      │     │
│    │   │   - Time-based correlation                   │      │     │
│    │   │   - Caching and optimization                 │      │     │
│    │   └──────────────────────────────────────────────┘      │     │
│    └──────────────────────────────────────────────────────────┘     │
│                            │                                         │
│                ┌───────────┴────────────┐                            │
│                │                        │                            │
│     ┌──────────▼──────────┐   ┌────────▼────────────────┐          │
│     │   TimescaleDB       │   │  External Data Adapters │          │
│     │   (Managed)         │   │  ┌──────────────────┐   │          │
│     │                     │   │  │  S3 Adapter      │   │          │
│     │  - Events table     │   │  │  ELK Adapter     │   │          │
│     │  - Metrics table    │   │  │  Zabbix Adapter  │   │          │
│     │  - Aggregates       │   │  │  CW Adapter      │   │          │
│     │  - Compression      │   │  │  Queue Adapter   │   │          │
│     │  - Retention        │   │  │  DB Adapter      │   │          │
│     └─────────────────────┘   │  └──────────────────┘   │          │
│                               └──────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        WEB UI LAYER                                  │
│                                                                       │
│    ┌──────────────────────────────────────────────────────────┐     │
│    │         Streamlit Dashboard (Enhanced)                   │     │
│    │                                                          │     │
│    │   Data Sources Configuration:                           │     │
│    │   ┌─────────────────────────────────────────────┐       │     │
│    │   │  Primary: TimescaleDB (managed)             │       │     │
│    │   │  Secondary: External sources                │       │     │
│    │   │    ├─ S3 archives                           │       │     │
│    │   │    ├─ ELK logs                              │       │     │
│    │   │    ├─ Zabbix metrics                        │       │     │
│    │   │    └─ CloudWatch                            │       │     │
│    │   └─────────────────────────────────────────────┘       │     │
│    │                                                          │     │
│    │   Views:                                                │     │
│    │   ├─ Real-time Monitoring (managed data)               │     │
│    │   ├─ Historical Analysis (managed + external)           │     │
│    │   ├─ Multi-Source Comparison                            │     │
│    │   ├─ Alerting & Notifications                           │     │
│    │   └─ System Health Dashboard                            │     │
│    └──────────────────────────────────────────────────────────┘     │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Component Details

### 1. Multi-Language SDK Architecture

All SDKs follow a **common interface** but are implemented idiomatically for each language.

#### Common SDK Interface

```
initialize(config)
  └─> Load configuration
  └─> Initialize backend clients
  └─> Validate configuration

emit_event(event)
  └─> Serialize event
  └─> Route to backend(s)
  └─> Handle errors/retries

emit_batch(events)
  └─> Batch events
  └─> Route to backend(s)
  └─> Return results

monitored_context(name, metadata)
  └─> Start event
  └─> Progress events
  └─> Finish/Error event

close()
  └─> Flush pending events
  └─> Close connections
```

#### Language-Specific Implementation Locations

```
components/monitoring/sdk/
├── python/
│   ├── monitoring_sdk/
│   │   ├── __init__.py
│   │   ├── emitter.py (enhanced with routing)
│   │   ├── config.py (new universal config)
│   │   ├── backends/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── sidecar.py
│   │   │   ├── filesystem.py
│   │   │   ├── s3.py
│   │   │   ├── elk.py
│   │   │   ├── zabbix.py
│   │   │   ├── cloudwatch.py
│   │   │   └── queue.py
│   │   └── context.py
│   └── setup.py
├── c/
│   ├── include/
│   │   └── monitoring.h
│   ├── src/
│   │   ├── monitoring.c
│   │   ├── config.c
│   │   ├── backends/
│   │   │   ├── sidecar.c
│   │   │   ├── filesystem.c
│   │   │   ├── http.c (for ELK, webhooks)
│   │   │   └── s3.c (via libcurl + AWS SDK)
│   │   └── utils.c
│   ├── CMakeLists.txt
│   └── README.md
├── r/
│   ├── R/
│   │   ├── monitoring.R
│   │   ├── config.R
│   │   ├── backends.R
│   │   └── context.R
│   ├── DESCRIPTION
│   ├── NAMESPACE
│   └── README.md
├── perl/
│   ├── lib/
│   │   └── Monitoring/
│   │       ├── SDK.pm
│   │       ├── Config.pm
│   │       ├── Backends/
│   │       │   ├── Sidecar.pm
│   │       │   ├── FileSystem.pm
│   │       │   ├── S3.pm
│   │       │   └── HTTP.pm
│   │       └── Context.pm
│   ├── Makefile.PL
│   └── README.md
└── java/
    ├── src/main/java/com/wafermonitor/sdk/
    │   ├── Monitoring.java
    │   ├── Config.java
    │   ├── Emitter.java
    │   ├── backends/
    │   │   ├── Backend.java (interface)
    │   │   ├── SidecarBackend.java
    │   │   ├── FileSystemBackend.java
    │   │   ├── S3Backend.java
    │   │   ├── ELKBackend.java
    │   │   └── ZabbixBackend.java
    │   └── Context.java
    ├── pom.xml
    └── README.md
```

### 2. Universal Configuration Format

**File**: `monitoring-config.yaml` (or JSON, env vars)

```yaml
# Universal SDK Configuration
sdk:
  mode: sidecar  # or "direct"
  
  # Sidecar mode configuration
  sidecar:
    url: http://localhost:17000
    timeout: 5.0
    retries: 3
    enable_spooling: true
    spool_dir: /tmp/sdk-spool
  
  # Direct mode configuration
  direct_backends:
    - type: filesystem
      enabled: true
      priority: 1
      config:
        path: /data/monitoring
        format: jsonl
        rotate_size_mb: 100
    
    - type: s3
      enabled: true
      priority: 2
      config:
        bucket: monitoring-events
        region: us-east-1
        prefix: events/
        credentials:
          access_key_id: ${AWS_ACCESS_KEY_ID}
          secret_access_key: ${AWS_SECRET_ACCESS_KEY}
    
    - type: elk
      enabled: true
      priority: 3
      config:
        url: http://elasticsearch:9200
        index: monitoring
        username: ${ELK_USER}
        password: ${ELK_PASSWORD}
    
    - type: zabbix
      enabled: false
      priority: 4
      config:
        url: http://zabbix:10051
        host: wafer-monitor
        api_key: ${ZABBIX_API_KEY}
  
  # Application metadata
  app:
    name: wafer-processing
    version: 1.0.0
    site_id: fab1
    instance_id: ${HOSTNAME}
```

### 3. Sidecar Backend Router

**Architecture**: Pluggable backend system with priority-based routing

**File**: `components/monitoring/sidecar/backend_router.py`

```python
class BackendRouter:
    """
    Routes events to multiple backends based on configuration.
    
    Features:
    - Priority-based routing
    - Concurrent delivery (async)
    - Fallback on failure
    - Circuit breaker pattern
    - Metrics collection
    """
    
    def __init__(self, config: SidecarConfig):
        self.backends = []
        self.load_backends(config)
    
    def load_backends(self, config):
        """Load and initialize backends from config."""
        for backend_config in config.backends:
            backend_class = BACKEND_REGISTRY[backend_config.type]
            backend = backend_class(backend_config)
            self.backends.append(backend)
    
    async def route_event(self, event: Dict) -> Dict[str, bool]:
        """
        Route event to all enabled backends concurrently.
        
        Returns:
            Dict mapping backend name to success status
        """
        tasks = []
        for backend in self.backends:
            if backend.is_enabled():
                task = asyncio.create_task(
                    self._send_with_circuit_breaker(backend, event)
                )
                tasks.append((backend.name, task))
        
        results = {}
        for name, task in tasks:
            try:
                success = await task
                results[name] = success
            except Exception as e:
                logger.error(f"Backend {name} failed", error=str(e))
                results[name] = False
        
        return results
```

### 4. API Gateway Dual Endpoints

**File**: `components/data-plane/api-gateway/main.py`

```python
from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any

app = FastAPI(title="Wafer Monitor API Gateway")

# ===== MANAGED ENDPOINT =====
@app.post("/v1/ingest/managed")
async def ingest_managed(events: List[Dict[str, Any]]):
    """
    Ingest events into managed TimescaleDB.
    
    Used by: Sidecar, Direct SDK (managed mode)
    Target: TimescaleDB
    """
    async with db_pool.acquire() as conn:
        await conn.executemany(
            "INSERT INTO events (...) VALUES (...)",
            events
        )
    return {"status": "ok", "ingested": len(events)}

# ===== EXTERNAL QUERY ENDPOINT =====
@app.post("/v1/query/external")
async def query_external(
    source: str,
    time_range: Dict[str, str],
    filters: Dict[str, Any]
):
    """
    Query external data sources.
    
    Supported sources: s3, elk, zabbix, cloudwatch
    Returns: Unified event format
    """
    adapter = ADAPTER_REGISTRY[source]
    results = await adapter.query(time_range, filters)
    return {"source": source, "events": results}

# ===== UNIFIED DATA ENDPOINT =====
@app.get("/v1/data/unified")
async def get_unified_data(
    site_id: str,
    start: str,
    end: str,
    sources: List[str] = ["managed", "s3", "elk"]
):
    """
    Get unified data from multiple sources.
    
    Combines:
    - Managed data (TimescaleDB)
    - External data (S3, ELK, etc.)
    
    Returns: Merged and deduplicated events
    """
    tasks = []
    
    # Query managed data
    if "managed" in sources:
        tasks.append(query_managed(site_id, start, end))
    
    # Query external sources
    for source in sources:
        if source != "managed":
            adapter = ADAPTER_REGISTRY.get(source)
            if adapter:
                tasks.append(adapter.query({
                    "start": start,
                    "end": end,
                    "site_id": site_id
                }))
    
    results = await asyncio.gather(*tasks)
    merged = merge_and_deduplicate(results)
    
    return {
        "site_id": site_id,
        "time_range": {"start": start, "end": end},
        "sources": sources,
        "events": merged,
        "count": len(merged)
    }
```

### 5. External Data Adapters

**File**: `components/data-plane/api-gateway/adapters/`

```python
# Base adapter interface
class DataAdapter(ABC):
    @abstractmethod
    async def query(
        self,
        time_range: Dict[str, str],
        filters: Dict[str, Any]
    ) -> List[Dict]:
        """Query external source and return unified events."""
        pass

# S3 Adapter
class S3Adapter(DataAdapter):
    async def query(self, time_range, filters):
        """Read Parquet files from S3."""
        s3_client = boto3.client('s3')
        # List objects in time range
        # Read Parquet files
        # Convert to unified format
        return events

# ELK Adapter
class ELKAdapter(DataAdapter):
    async def query(self, time_range, filters):
        """Query Elasticsearch."""
        es = Elasticsearch([self.url])
        query = {
            "query": {
                "range": {
                    "timestamp": {
                        "gte": time_range["start"],
                        "lte": time_range["end"]
                    }
                }
            }
        }
        results = es.search(index=self.index, body=query)
        return self._convert_to_unified(results)

# Similar adapters for Zabbix, CloudWatch, etc.
```

---

## 🔄 Data Flow Scenarios

### Scenario 1: SDK → Sidecar → Managed DB
```
Python App
  → Python SDK (mode: sidecar)
  → HTTP POST to Sidecar :17000
  → Sidecar routes to Managed API backend
  → API Gateway POST /v1/ingest/managed
  → TimescaleDB
  → Web UI queries managed data
```

### Scenario 2: SDK → Direct → S3
```
Java App
  → Java SDK (mode: direct, backend: s3)
  → Direct S3 upload
  → API Gateway POST /v1/query/external (source: s3)
  → S3 Adapter reads Parquet
  → Web UI shows S3 data
```

### Scenario 3: SDK → Sidecar → Multiple Backends
```
C App
  → C SDK (mode: sidecar)
  → HTTP POST to Sidecar :17000
  → Sidecar routes to:
      ├─> Managed API (priority 1)
      ├─> File System (priority 2, backup)
      └─> S3 (priority 3, archive)
  → Web UI can query from any source
```

### Scenario 4: Unified Multi-Source View
```
Web UI
  → GET /v1/data/unified?sources=managed,s3,elk
  → API Gateway:
      ├─> Query TimescaleDB (managed)
      ├─> Query S3 via S3Adapter
      └─> Query ELK via ELKAdapter
  → Merge results
  → Return unified view
```

---

## 📋 Implementation Plan

### Week 1: SDK Foundation
- [ ] Design universal SDK interface
- [ ] Implement Python SDK enhancements
- [ ] Create SDK configuration system
- [ ] Add backend routing to Python SDK
- [ ] Tests for Python SDK

### Week 2: C SDK
- [ ] Implement C SDK core
- [ ] Add HTTP client (libcurl)
- [ ] Add JSON serialization (cJSON)
- [ ] Add backends: sidecar, filesystem, S3
- [ ] Tests for C SDK

### Week 3: R, Perl, Java SDKs
- [ ] Implement R SDK (httr, jsonlite)
- [ ] Implement Perl SDK (LWP, JSON)
- [ ] Implement Java SDK (HttpClient, Jackson)
- [ ] Tests for all SDKs

### Week 4: Sidecar Enhancement
- [ ] Implement Backend Router
- [ ] Add pluggable backend system
- [ ] Implement 8 backend types
- [ ] Add circuit breaker
- [ ] Tests for sidecar

### Week 5: API Gateway
- [ ] Split API into managed/external
- [ ] Implement dual endpoints
- [ ] Create data adapters
- [ ] Implement unified endpoint
- [ ] Tests for API

### Week 6: Integration & Documentation
- [ ] End-to-end testing
- [ ] Performance testing
- [ ] Documentation
- [ ] Examples for all SDKs
- [ ] Deployment guides

---

## ✅ Success Metrics

1. **SDK Availability**
   - ✅ Python SDK enhanced with routing
   - ✅ C SDK with 5+ backends
   - ✅ R SDK fully functional
   - ✅ Perl SDK fully functional
   - ✅ Java SDK fully functional

2. **Backend Support**
   - ✅ 8+ backend types supported
   - ✅ All backends tested
   - ✅ Circuit breaker implemented
   - ✅ < 100ms p99 latency

3. **API Capabilities**
   - ✅ Dual endpoints (managed + external)
   - ✅ 5+ external adapters
   - ✅ Unified data merging
   - ✅ < 200ms query latency

4. **Documentation**
   - ✅ SDK docs for each language
   - ✅ Configuration guide
   - ✅ Deployment guide
   - ✅ 10+ examples

---

**Status**: Design Complete  
**Next Step**: Begin implementation  
**Date**: 2025-10-20

