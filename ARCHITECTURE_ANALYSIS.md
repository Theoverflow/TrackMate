# Current Architecture Analysis

## 📊 Current State (Before Enhancement)

### Component Structure
```
wafer-monitor-v2/
├── components/
│   ├── monitoring/
│   │   ├── sdk/           # Python SDK only
│   │   └── sidecar/       # Forwarding agent
│   ├── data-plane/
│   │   ├── local-api/     # Single ingest endpoint
│   │   ├── central-api/   # Aggregator
│   │   ├── archiver/      # S3 archival
│   │   └── database/      # TimescaleDB
│   └── web/
│       ├── local-dashboard/
│       └── central-dashboard/
└── shared/
    └── shared_utils/
        └── integrations/  # Backend integrations (Zabbix, ELK, etc.)
```

### Current Flow
```
Business App (Python only)
      ↓
   SDK (Python)
      ↓
   HTTP POST /v1/ingest/events
      ↓
   Sidecar Agent
      ↓
   HTTP POST to Local API
      ↓
   TimescaleDB (managed)
      ↓
   Web UI
```

### Current SDK (Python Only)
- **Language**: Python only
- **Target**: Sidecar agent via HTTP
- **Configuration**: Environment variable (SIDECAR_URL)
- **Features**: Retries, structured logging, connection pooling

### Current Sidecar
- **Function**: HTTP proxy to Local API
- **Features**: Spooling, retry logic
- **Limitation**: Only forwards to Local API

### Current Integrations (shared_utils/integrations/)
- ✅ Local API
- ✅ Zabbix
- ✅ ELK/Elasticsearch
- ✅ CSV Export
- ✅ JSON Export
- ✅ Webhook
- ✅ AWS CloudWatch
- ✅ AWS X-Ray

**Problem**: Integrations exist but are only used by sidecar, not by SDK directly

### Current API
- **Single endpoint**: `/v1/ingest/events`
- **Target**: TimescaleDB only
- **Limitation**: No support for external data sources

---

## 🎯 Requirements for New Architecture

### 1. Multi-Language SDK Support
**Required SDKs**:
- ✅ Python (existing, enhance)
- 🆕 C
- 🆕 R
- 🆕 Perl
- 🆕 Java

### 2. Flexible SDK Configuration
SDKs should support **two modes**:

#### Mode A: Via Sidecar (Proxy Pattern)
```
SDK → Sidecar → Backend(s)
```
- SDK sends to local sidecar
- Sidecar routes to configured backend(s)

#### Mode B: Direct to Backend (Direct Pattern)
```
SDK → Backend (FS, S3, ELK, Zabbix, AWS, etc.)
```
- SDK bypasses sidecar
- SDK writes directly to backend

### 3. Pluggable Sidecar Backends
Sidecar should support multiple backends:

#### Managed Backend (Current)
```
Sidecar → API Gateway → TimescaleDB
```

#### External Backends (New)
```
Sidecar → File System (local/NFS)
Sidecar → S3 (direct upload)
Sidecar → ELK/Loki (HTTP)
Sidecar → Zabbix (Zabbix API)
Sidecar → AWS CloudWatch
Sidecar → Message Queue (Kafka, RabbitMQ, SQS)
Sidecar → Other Database (MySQL, MongoDB, Cassandra)
```

### 4. Dual API Endpoints

#### Endpoint 1: Managed Service Ingestion
```
POST /v1/ingest/managed
```
- Receives events from sidecar/SDK
- Writes to local TimescaleDB
- For on-premise managed monitoring

#### Endpoint 2: External Service Query
```
POST /v1/query/external
```
- Queries external data sources
- Aggregates data from multiple backends
- For hybrid/cloud scenarios

### 5. Web UI Access
```
Web UI → API Server → {
    Managed Data (TimescaleDB)
    External Data (via adapters)
}
```
- Web UI in separate environment
- Access both managed and external data
- Unified view

---

## 🏗️ Proposed New Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BUSINESS LAYER                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐ │
│  │ Python   │  │   Java   │  │    C     │  │    R     │  │ Perl │ │
│  │ App      │  │   App    │  │   App    │  │   App    │  │ App  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬──┘ │
│       │             │              │              │             │    │
│  ┌────▼─────┐  ┌───▼──────┐  ┌───▼──────┐  ┌───▼──────┐  ┌──▼───┐ │
│  │Python SDK│  │ Java SDK │  │  C SDK   │  │  R SDK   │  │Perl  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │SDK   │ │
│       │             │              │              │        └──┬───┘ │
└───────┼─────────────┼──────────────┼──────────────┼───────────┼─────┘
        │             │              │              │           │
        └─────────────┴──────────────┴──────────────┴───────────┘
                               ↓
        ┌──────────────────────────────────────────────────────┐
        │              SDK ROUTING LOGIC                        │
        │  Config: mode = "sidecar" | "direct"                 │
        │  Config: backends = [...]                            │
        └──────────────────────────────────────────────────────┘
                               ↓
                    ┌──────────┴──────────┐
                    │                     │
            ┌───────▼────────┐    ┌──────▼──────────────────────┐
            │   Via Sidecar  │    │   Direct to Backend         │
            └───────┬────────┘    └──────┬──────────────────────┘
                    │                    │
                    ↓                    ↓
        ┌───────────────────────┐   ┌─────────────────────────┐
        │   SIDECAR AGENT       │   │   DIRECT BACKENDS       │
        │   (Env A)             │   │   - File System         │
        │                       │   │   - S3                  │
        │   Backend Router:     │   │   - ELK/Loki            │
        │   ├─> Managed API     │   │   - Zabbix              │
        │   ├─> File System     │   │   - AWS CloudWatch      │
        │   ├─> S3              │   │   - Kafka/SQS           │
        │   ├─> ELK             │   │   - Custom Webhook      │
        │   ├─> Zabbix          │   └─────────────────────────┘
        │   ├─> CloudWatch      │
        │   └─> Queue           │
        └──────────┬────────────┘
                   │
                   ↓
        ┌──────────────────────────────────────────────────────┐
        │            DATA PLANE LAYER (Env B)                  │
        │  ┌───────────────────────────────────────────────┐   │
        │  │         API GATEWAY                           │   │
        │  │                                               │   │
        │  │  POST /v1/ingest/managed                      │   │
        │  │   └─> Write to TimescaleDB                    │   │
        │  │                                               │   │
        │  │  POST /v1/query/external                      │   │
        │  │   └─> Query external backends via adapters    │   │
        │  │                                               │   │
        │  │  GET /v1/data/unified                         │   │
        │  │   └─> Merge managed + external data           │   │
        │  └───────────────────────────────────────────────┘   │
        │           │                    │                      │
        │           ↓                    ↓                      │
        │  ┌────────────────┐   ┌──────────────────┐          │
        │  │  TimescaleDB   │   │ External Adapters│          │
        │  │  (Managed)     │   │ - S3 Reader      │          │
        │  └────────────────┘   │ - ELK Reader     │          │
        │                       │ - Zabbix Reader  │          │
        │                       └──────────────────┘          │
        └──────────────────────────────────────────────────────┘
                               ↓
        ┌──────────────────────────────────────────────────────┐
        │            WEB UI LAYER (Env C)                      │
        │  ┌───────────────────────────────────────────────┐   │
        │  │         Streamlit Dashboard                   │   │
        │  │                                               │   │
        │  │  Data Sources:                                │   │
        │  │  ├─> Managed (TimescaleDB)                    │   │
        │  │  └─> External (S3, ELK, etc.)                 │   │
        │  │                                               │   │
        │  │  Views:                                       │   │
        │  │  ├─> Real-time monitoring                     │   │
        │  │  ├─> Historical analysis                      │   │
        │  │  └─> Multi-source comparison                  │   │
        │  └───────────────────────────────────────────────┘   │
        └──────────────────────────────────────────────────────┘
```

---

## 🔧 Key Design Decisions

### 1. SDK Configuration Schema (Universal)
```json
{
  "mode": "sidecar" | "direct",
  "sidecar": {
    "url": "http://localhost:17000",
    "timeout": 5.0,
    "retries": 3
  },
  "direct_backends": [
    {
      "type": "filesystem",
      "path": "/data/monitoring",
      "format": "jsonl"
    },
    {
      "type": "s3",
      "bucket": "monitoring-events",
      "region": "us-east-1"
    },
    {
      "type": "elk",
      "url": "http://elasticsearch:9200",
      "index": "monitoring"
    }
  ],
  "app": {
    "name": "wafer-processing",
    "version": "1.0.0",
    "site_id": "fab1"
  }
}
```

### 2. Sidecar Configuration Schema
```json
{
  "ingest": {
    "port": 17000,
    "max_batch_size": 100,
    "flush_interval": 5
  },
  "backends": [
    {
      "type": "managed_api",
      "enabled": true,
      "url": "http://local-api:18000",
      "endpoint": "/v1/ingest/managed",
      "priority": 1
    },
    {
      "type": "filesystem",
      "enabled": true,
      "path": "/backup/events",
      "format": "jsonl",
      "priority": 2
    },
    {
      "type": "s3",
      "enabled": false,
      "bucket": "events-backup",
      "region": "us-east-1",
      "priority": 3
    }
  ],
  "spool": {
    "enabled": true,
    "path": "/tmp/sidecar-spool",
    "max_size_mb": 1000
  }
}
```

### 3. API Gateway Schema
```python
# Managed endpoint
POST /v1/ingest/managed
{
  "events": [...],
  "source": "sidecar",
  "site_id": "fab1"
}

# External query endpoint
POST /v1/query/external
{
  "source": "s3" | "elk" | "zabbix",
  "time_range": {
    "start": "2025-01-01T00:00:00Z",
    "end": "2025-01-02T00:00:00Z"
  },
  "filters": {...}
}

# Unified data endpoint
GET /v1/data/unified?site_id=fab1&start=...&end=...
# Returns merged data from managed + all external sources
```

---

## 📋 Implementation Roadmap

### Phase 1: SDK Layer
1. Design universal SDK interface
2. Implement Python SDK enhancements
3. Implement C SDK
4. Implement R SDK
5. Implement Perl SDK
6. Implement Java SDK
7. Create SDK configuration system

### Phase 2: Sidecar Enhancement
1. Design pluggable backend system
2. Implement backend router
3. Add filesystem backend
4. Add S3 backend
5. Add ELK/Loki backend
6. Add Zabbix backend
7. Add queue backends (Kafka, SQS)
8. Add external DB backends

### Phase 3: API Gateway
1. Split current API into managed/external
2. Implement managed ingest endpoint
3. Implement external query endpoint
4. Create data adapters for external sources
5. Implement unified data endpoint
6. Add query optimization and caching

### Phase 4: Integration & Testing
1. End-to-end tests for all SDKs
2. Integration tests for all backends
3. Performance testing
4. Documentation and examples

---

## 🎯 Success Criteria

✅ SDKs available in 5 languages (Python, C, R, Perl, Java)
✅ SDKs support both sidecar and direct modes
✅ Sidecar supports 8+ backend types
✅ API supports both managed and external data
✅ Web UI can display data from all sources
✅ Configuration is consistent and well-documented
✅ All integrations are tested
✅ Performance meets SLAs (< 100ms p99 latency)

---

**Status**: Analysis Complete
**Next Step**: Design and implement new architecture
**Date**: 2025-10-20

