# API Documentation

## Sidecar Agent API

**Base URL:** `http://localhost:8000`

### POST /v1/ingest/events

Ingest a single monitoring event.

**Request Body:**
```json
{
  "idempotency_key": "uuid",
  "site_id": "fab1",
  "app": {
    "app_id": "uuid",
    "name": "app-name",
    "version": "1.0.0"
  },
  "entity": {
    "type": "job",
    "id": "uuid",
    "parent_id": null,
    "business_key": "batch-123",
    "sub_key": null
  },
  "event": {
    "kind": "started",
    "at": "2025-10-19T12:00:00Z",
    "status": "running",
    "metrics": {},
    "metadata": {}
  }
}
```

**Response:**
```json
{
  "ok": true
}
```

### POST /v1/ingest/events:batch

Ingest multiple events in a batch.

**Request Body:** Array of events (same format as single event)

**Response:**
```json
{
  "ok": true,
  "forwarded": 95,
  "spooled": 5
}
```

### GET /v1/healthz

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "sidecar-agent",
  "version": "2.0.0",
  "spool_count": 0,
  "spool_dir": "/tmp/sidecar-spool"
}
```

### GET /metrics

Prometheus metrics endpoint.

## Local API

**Base URL:** `http://localhost:18000`

### POST /v1/ingest/events

Ingest event into TimescaleDB (typically called by Sidecar Agent).

### GET /v1/jobs

Query jobs with filtering.

**Query Parameters:**
- `from` (optional) - Start timestamp (ISO 8601)
- `to` (optional) - End timestamp (ISO 8601)
- `status` (optional) - Comma-separated status values
- `app_name` (optional) - Filter by app name (contains)
- `limit` (optional, default: 1000) - Result limit

**Response:**
```json
{
  "items": [
    {
      "job_id": "uuid",
      "app_id": "uuid",
      "app_name": "processor",
      "app_version": "1.0.0",
      "site_id": "fab1",
      "job_key": "batch-123",
      "status": "succeeded",
      "started_at": "2025-10-19T12:00:00Z",
      "ended_at": "2025-10-19T12:05:00Z",
      "duration_s": 300.5,
      "cpu_user_s": 120.3,
      "cpu_system_s": 10.2,
      "mem_max_mb": 2048.5,
      "metadata": {},
      "inserted_at": "2025-10-19T12:05:01Z"
    }
  ],
  "count": 1,
  "duration_s": 0.023
}
```

### GET /v1/subjobs

Query subjobs (similar parameters and response to /v1/jobs).

### GET /v1/stream

Real-time event stream using Server-Sent Events (SSE).

**Response:** Stream of events in SSE format
```
data: {"at": "...", "entity_type": "job", ...}

data: {"at": "...", "entity_type": "subjob", ...}
```

### GET /v1/healthz

Health check with database status.

### GET /metrics

Prometheus metrics.

## Central API

**Base URL:** `http://localhost:19000`

### GET /v1/jobs

Query jobs from a specific site.

**Query Parameters:**
- `site` (required) - Site identifier
- All other parameters same as Local API

### GET /v1/subjobs

Query subjobs from a specific site.

**Query Parameters:**
- `site` (required) - Site identifier
- All other parameters same as Local API

### GET /v1/sites

List all configured sites.

**Response:**
```json
{
  "sites": [
    {
      "id": "fab1",
      "endpoint": "http://site1:18000"
    },
    {
      "id": "fab2",
      "endpoint": "http://site2:18000"
    }
  ],
  "count": 2
}
```

### GET /v1/healthz

Health check including status of all configured sites.

**Response:**
```json
{
  "status": "ok",
  "service": "central-api",
  "version": "2.0.0",
  "sites": {
    "fab1": {
      "status": "ok",
      "endpoint": "http://site1:18000"
    },
    "fab2": {
      "status": "degraded",
      "endpoint": "http://site2:18000",
      "error": "Connection timeout"
    }
  }
}
```

## Event Kinds

- `started` - Job/subjob started
- `progress` - Progress update during execution
- `metric` - Metric update
- `finished` - Job/subjob completed (succeeded or failed)
- `error` - Error occurred
- `canceled` - Job/subjob was canceled

## Status Values

- `running` - Currently executing
- `succeeded` - Completed successfully
- `failed` - Completed with error
- `canceled` - Was canceled before completion

## Metrics

All jobs and subjobs collect these metrics:

- `duration_s` - Total execution time in seconds
- `cpu_user_s` - CPU user time in seconds
- `cpu_system_s` - CPU system time in seconds
- `mem_max_mb` - Peak memory usage in megabytes

