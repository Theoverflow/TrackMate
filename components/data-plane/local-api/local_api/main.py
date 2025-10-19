"""
Local API - Event ingestion and query service with TimescaleDB.

Receives events from the Sidecar Agent and stores them in TimescaleDB.
Provides query endpoints for retrieving jobs, subjobs, and event streams.
"""
import os
import asyncio
import asyncpg
import json
import time
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone, timedelta

# Import shared utilities
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_utils import setup_logging, get_logger, setup_tracing, instrument_fastapi
from shared_utils import MetricsCollector, get_metrics_collector, trace_async
from shared_utils import LocalAPIConfig

# Configuration
config = LocalAPIConfig()

# Setup observability
setup_logging(config.service_name, level=config.log_level, json_logs=config.json_logs)
logger = get_logger(__name__)

if config.enable_tracing:
    tracer = setup_tracing(config.service_name, config.otlp_endpoint)
else:
    tracer = None

# Initialize metrics collector
metrics = get_metrics_collector(config.service_name)

# FastAPI app
app = FastAPI(
    title='Local Site API',
    version='2.0.0',
    description='Event ingestion and query service with TimescaleDB'
)

# Instrument with tracing
if config.enable_tracing:
    instrument_fastapi(app)


class IngestEvent(BaseModel):
    """Event model for ingestion."""
    idempotency_key: str
    site_id: str
    app: dict
    entity: dict
    event: dict


class JobResponse(BaseModel):
    """Response model for jobs query."""
    items: List[dict]
    count: int = Field(description="Number of items returned")


class SubjobResponse(BaseModel):
    """Response model for subjobs query."""
    items: List[dict]
    count: int = Field(description="Number of items returned")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to collect HTTP metrics."""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    metrics.record_http_request(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
        duration=duration
    )
    
    return response


async def get_pool() -> asyncpg.Pool:
    """
    Get or create the database connection pool.
    
    Returns:
        Connection pool instance
    """
    if not hasattr(app.state, 'pool'):
        logger.info(
            "creating_db_pool",
            min_size=config.db_pool_min_size,
            max_size=config.db_pool_max_size
        )
        app.state.pool = await asyncpg.create_pool(
            config.database_url,
            min_size=config.db_pool_min_size,
            max_size=config.db_pool_max_size
        )
        logger.info("db_pool_created")
    
    # Update pool metrics
    pool: asyncpg.Pool = app.state.pool
    metrics.update_pool_metrics(pool.get_size(), pool.get_idle_size())
    
    return app.state.pool


@app.on_event('startup')
async def startup() -> None:
    """Startup handler - initialize database pool."""
    logger.info("service_starting", database_url=config.database_url.split('@')[-1])
    await get_pool()
    logger.info("service_started")


@app.on_event('shutdown')
async def shutdown() -> None:
    """Shutdown handler - close database pool."""
    logger.info("service_shutting_down")
    if hasattr(app.state, 'pool'):
        await app.state.pool.close()
        logger.info("db_pool_closed")


@app.post('/v1/ingest/events', response_model=dict)
@trace_async("ingest_event")
async def ingest(ev: IngestEvent) -> JSONResponse:
    """
    Ingest a single monitoring event.
    
    Validates event timestamp, inserts into TimescaleDB tables,
    and ensures idempotency.
    
    Args:
        ev: Event to ingest
        
    Returns:
        Success response
        
    Raises:
        HTTPException: If event validation or insertion fails
    """
    start_time = time.time()
    now = datetime.now(timezone.utc)
    
    try:
        ev_at = datetime.fromisoformat(ev.event['at'])
    except (KeyError, ValueError) as e:
        logger.error("invalid_event_timestamp", error=str(e))
        raise HTTPException(status_code=422, detail='Invalid event timestamp')
    
    # Validate time skew
    skew = abs((now - ev_at).total_seconds())
    if skew > config.max_skew_s:
        logger.warning(
            "event_time_skew_exceeded",
            skew_s=skew,
            max_skew_s=config.max_skew_s
        )
        raise HTTPException(status_code=422, detail=f'Event time skew too large: {skew}s')
    
    pool = await get_pool()
    
    try:
        async with pool.acquire() as con:
            async with con.transaction():
                # Insert event
                db_start = time.time()
                await con.execute("""
                    INSERT INTO event(at, entity_type, entity_id, app_id, site_id, kind, payload, idempotency_key)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8)
                    ON CONFLICT (idempotency_key) DO NOTHING
                """, ev_at, ev.entity['type'], ev.entity['id'], ev.app['app_id'], ev.site_id,
                     ev.event['kind'], json.dumps(ev.event), ev.idempotency_key)
                
                metrics.record_db_operation(
                    'insert',
                    'event',
                    'success',
                    time.time() - db_start
                )
                
                # Insert app
                db_start = time.time()
                await con.execute("""
                    INSERT INTO app(app_id, name, version, site_id)
                    VALUES($1,$2,$3,$4)
                    ON CONFLICT (app_id) DO NOTHING
                """, ev.app['app_id'], ev.app.get('name', ''), ev.app.get('version', ''), ev.site_id)
                
                metrics.record_db_operation(
                    'insert',
                    'app',
                    'success',
                    time.time() - db_start
                )
                
                # Insert job or subjob
                if ev.entity['type'] == 'job':
                    db_start = time.time()
                    await con.execute("""
                        INSERT INTO job(job_id, app_id, site_id, job_key, status, started_at, ended_at, duration_s,
                                         cpu_user_s, cpu_system_s, mem_max_mb, metadata)
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    """, ev.entity['id'], ev.app['app_id'], ev.site_id, ev.entity.get('business_key', ''),
                         ev.event.get('status', 'running'),
                         ev.event.get('started_at'), ev.event.get('ended_at'),
                         (ev.event.get('metrics') or {}).get('duration_s'),
                         (ev.event.get('metrics') or {}).get('cpu_user_s', 0.0),
                         (ev.event.get('metrics') or {}).get('cpu_system_s', 0.0),
                         (ev.event.get('metrics') or {}).get('mem_max_mb', 0.0),
                         json.dumps(ev.event.get('metadata', {})))
                    
                    metrics.record_db_operation(
                        'insert',
                        'job',
                        'success',
                        time.time() - db_start
                    )
                else:
                    db_start = time.time()
                    await con.execute("""
                        INSERT INTO subjob(subjob_id, job_id, app_id, site_id, sub_key, status, started_at, ended_at, duration_s,
                                           cpu_user_s, cpu_system_s, mem_max_mb, metadata)
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    """, ev.entity['id'], ev.entity.get('parent_id'), ev.app['app_id'], ev.site_id,
                         ev.entity.get('sub_key', ''),
                         ev.event.get('status', 'running'), ev.event.get('started_at'), ev.event.get('ended_at'),
                         (ev.event.get('metrics') or {}).get('duration_s'),
                         (ev.event.get('metrics') or {}).get('cpu_user_s', 0.0),
                         (ev.event.get('metrics') or {}).get('cpu_system_s', 0.0),
                         (ev.event.get('metrics') or {}).get('mem_max_mb', 0.0),
                         json.dumps(ev.event.get('metadata', {})))
                    
                    metrics.record_db_operation(
                        'insert',
                        'subjob',
                        'success',
                        time.time() - db_start
                    )
        
        duration = time.time() - start_time
        logger.info(
            "event_ingested",
            event_kind=ev.event['kind'],
            entity_type=ev.entity['type'],
            site_id=ev.site_id,
            duration_s=round(duration, 4)
        )
        
        return JSONResponse({'ok': True, 'duration_s': round(duration, 4)})
    
    except Exception as e:
        logger.error(
            "event_ingestion_failed",
            error=str(e),
            error_type=type(e).__name__,
            idempotency_key=ev.idempotency_key
        )
        metrics.record_db_operation('insert', 'event', 'failed', 0)
        raise HTTPException(status_code=500, detail=f'Ingestion failed: {str(e)}')


@app.post('/v1/ingest/events:batch', response_model=dict)
@trace_async("ingest_batch")
async def ingest_batch(events: List[IngestEvent]) -> JSONResponse:
    """
    Ingest a batch of events.
    
    Args:
        events: List of events to ingest
        
    Returns:
        Response with ingestion statistics
    """
    logger.info("batch_ingestion_started", count=len(events))
    
    success = 0
    failed = 0
    
    for ev in events:
        try:
            await ingest(ev)
            success += 1
        except HTTPException:
            failed += 1
    
    logger.info(
        "batch_ingestion_completed",
        total=len(events),
        success=success,
        failed=failed
    )
    
    return JSONResponse({
        'ok': True,
        'total': len(events),
        'success': success,
        'failed': failed
    })


@app.get('/v1/jobs', response_model=dict)
@trace_async("get_jobs")
async def get_jobs(
    frm: Optional[str] = Query(None, alias='from', description="Start timestamp (ISO 8601)"),
    to: Optional[str] = Query(None, alias='to', description="End timestamp (ISO 8601)"),
    status: Optional[str] = Query(None, description="Comma-separated status values"),
    app_name: Optional[str] = Query(None, description="Filter by app name (contains)"),
    limit: int = Query(config.query_default_limit, ge=1, le=config.query_max_limit, description="Result limit")
) -> JSONResponse:
    """
    Query jobs with filtering.
    
    Args:
        frm: Start timestamp filter
        to: End timestamp filter
        status: Status filter (comma-separated)
        app_name: App name filter (contains match)
        limit: Result limit
        
    Returns:
        List of matching jobs
    """
    start_time = time.time()
    pool = await get_pool()
    
    clauses: List[str] = []
    params: List[any] = []
    
    if frm:
        clauses.append(f"j.inserted_at >= ${len(params) + 1}")
        params.append(datetime.fromisoformat(frm.replace('Z', '+00:00')))
    
    if to:
        clauses.append(f"j.inserted_at <= ${len(params) + 1}")
        params.append(datetime.fromisoformat(to.replace('Z', '+00:00')))
    
    if status:
        sts = [s.strip() for s in status.split(',') if s.strip()]
        clauses.append(f"j.status = ANY(${len(params) + 1})")
        params.append(sts)
    
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    
    sql = f'''
    WITH latest AS (
      SELECT j.*, ROW_NUMBER() OVER (PARTITION BY j.job_id ORDER BY j.inserted_at DESC) rn
      FROM job j
      {where}
    )
    SELECT l.*, a.name AS app_name, a.version AS app_version
    FROM latest l
    JOIN app a ON a.app_id = l.app_id
    WHERE l.rn = 1
    {'AND a.name ILIKE $' + str(len(params) + 1) if app_name else ''}
    ORDER BY l.inserted_at DESC
    LIMIT {int(limit)}
    '''
    
    if app_name:
        params.append(f"%{app_name}%")
    
    try:
        db_start = time.time()
        async with pool.acquire() as con:
            rows = await con.fetch(sql, *params)
        
        metrics.record_db_operation(
            'select',
            'job',
            'success',
            time.time() - db_start
        )
        
        items = [dict(r) for r in rows]
        
        duration = time.time() - start_time
        logger.info(
            "jobs_query_completed",
            count=len(items),
            duration_s=round(duration, 4)
        )
        
        return JSONResponse({
            'items': items,
            'count': len(items),
            'duration_s': round(duration, 4)
        })
    
    except Exception as e:
        logger.error("jobs_query_failed", error=str(e))
        metrics.record_db_operation('select', 'job', 'failed', 0)
        raise HTTPException(status_code=500, detail=f'Query failed: {str(e)}')


@app.get('/v1/subjobs', response_model=dict)
@trace_async("get_subjobs")
async def get_subjobs(
    frm: Optional[str] = Query(None, alias='from', description="Start timestamp (ISO 8601)"),
    to: Optional[str] = Query(None, alias='to', description="End timestamp (ISO 8601)"),
    status: Optional[str] = Query(None, description="Comma-separated status values"),
    limit: int = Query(config.query_default_limit, ge=1, le=config.query_max_limit, description="Result limit")
) -> JSONResponse:
    """
    Query subjobs with filtering.
    
    Args:
        frm: Start timestamp filter
        to: End timestamp filter
        status: Status filter (comma-separated)
        limit: Result limit
        
    Returns:
        List of matching subjobs
    """
    start_time = time.time()
    pool = await get_pool()
    
    clauses: List[str] = []
    params: List[any] = []
    
    if frm:
        clauses.append(f"s.inserted_at >= ${len(params) + 1}")
        params.append(datetime.fromisoformat(frm.replace('Z', '+00:00')))
    
    if to:
        clauses.append(f"s.inserted_at <= ${len(params) + 1}")
        params.append(datetime.fromisoformat(to.replace('Z', '+00:00')))
    
    if status:
        sts = [s.strip() for s in status.split(',') if s.strip()]
        clauses.append(f"s.status = ANY(${len(params) + 1})")
        params.append(sts)
    
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    
    sql = f'''
    WITH latest AS (
      SELECT s.*, ROW_NUMBER() OVER (PARTITION BY s.subjob_id ORDER BY s.inserted_at DESC) rn
      FROM subjob s
      {where}
    )
    SELECT * FROM latest WHERE rn = 1
    ORDER BY inserted_at DESC
    LIMIT {int(limit)}
    '''
    
    try:
        db_start = time.time()
        async with pool.acquire() as con:
            rows = await con.fetch(sql, *params)
        
        metrics.record_db_operation(
            'select',
            'subjob',
            'success',
            time.time() - db_start
        )
        
        items = [dict(r) for r in rows]
        
        duration = time.time() - start_time
        logger.info(
            "subjobs_query_completed",
            count=len(items),
            duration_s=round(duration, 4)
        )
        
        return JSONResponse({'items': items, 'count': len(items), 'duration_s': round(duration, 4)})
    
    except Exception as e:
        logger.error("subjobs_query_failed", error=str(e))
        metrics.record_db_operation('select', 'subjob', 'failed', 0)
        raise HTTPException(status_code=500, detail=f'Query failed: {str(e)}')


@app.get('/v1/stream')
async def stream() -> StreamingResponse:
    """
    Stream events in real-time using Server-Sent Events.
    
    Returns:
        SSE stream of new events
    """
    async def event_gen():
        pool = await get_pool()
        last = datetime.now(timezone.utc)
        logger.info("event_stream_started")
        
        try:
            while True:
                async with pool.acquire() as con:
                    rows = await con.fetch(
                        'SELECT at, entity_type, entity_id, site_id, kind, payload '
                        'FROM event WHERE at > $1 ORDER BY at',
                        last
                    )
                    if rows:
                        last = max(r['at'] for r in rows)
                        for r in rows:
                            yield f"data: {json.dumps(dict(r), default=str)}\n\n"
                
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("event_stream_cancelled")
    
    return StreamingResponse(event_gen(), media_type='text/event-stream')


@app.get('/v1/healthz')
async def healthz() -> JSONResponse:
    """Health check endpoint."""
    pool_ok = hasattr(app.state, 'pool')
    
    return JSONResponse({
        'status': 'ok' if pool_ok else 'degraded',
        'service': config.service_name,
        'version': '2.0.0',
        'database_pool': 'connected' if pool_ok else 'disconnected'
    })


@app.get('/metrics')
async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=metrics.get_metrics(),
        media_type=metrics.get_content_type()
    )


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=18000, log_config=None)
