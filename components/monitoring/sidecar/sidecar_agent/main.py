"""
Sidecar Agent - Event forwarding service with spooling support.

Forwards monitoring events from business applications to the Local API.
Provides resilience through local spooling when the Local API is unavailable.
"""
import os
import asyncio
import json
import httpx
import uuid
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import time

# Import shared utilities
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_utils import setup_logging, get_logger, setup_tracing, instrument_fastapi
from shared_utils import MetricsCollector, get_metrics_collector
from shared_utils import SidecarAgentConfig

# Configuration
config = SidecarAgentConfig()

# Setup observability
setup_logging(config.service_name, level=config.log_level, json_logs=config.json_logs)
logger = get_logger(__name__)

if config.enable_tracing:
    tracer = setup_tracing(config.service_name, config.otlp_endpoint)
else:
    tracer = None

# Initialize metrics collector
metrics = get_metrics_collector(config.service_name)

# Setup directories
SPOOL_DIR = Path(config.spool_dir)
SPOOL_DIR.mkdir(parents=True, exist_ok=True)

# FastAPI app
app = FastAPI(
    title='Sidecar Agent',
    version='2.0.0',
    description='Event forwarding service with resilience through local spooling'
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


async def forward(ev: dict) -> None:
    """
    Forward an event to the Local API.
    
    Args:
        ev: Event dict to forward
        
    Raises:
        httpx.HTTPError: If the request fails
    """
    async with httpx.AsyncClient(timeout=config.request_timeout_s) as client:
        try:
            logger.debug("forwarding_event", event_kind=ev.get('event', {}).get('kind'))
            r = await client.post(f'{config.local_api_base}/v1/ingest/events', json=ev)
            r.raise_for_status()
            metrics.record_event_processed('forward', 'success')
            logger.info(
                "event_forwarded",
                event_kind=ev.get('event', {}).get('kind'),
                status_code=r.status_code
            )
        except Exception as e:
            metrics.record_event_processed('forward', 'failed')
            logger.error(
                "forward_failed",
                event_kind=ev.get('event', {}).get('kind'),
                error=str(e),
                error_type=type(e).__name__
            )
            raise


def spool(ev: dict) -> None:
    """
    Spool an event to disk for later retry.
    
    Args:
        ev: Event dict to spool
    """
    try:
        idem_key = ev.get('idempotency_key', '') or str(uuid.uuid4())
        timestamp = int(time.time() * 1e6)
        fname = SPOOL_DIR / f"{idem_key}_{timestamp}.json"
        fname.write_text(json.dumps(ev), encoding='utf-8')
        metrics.record_event_processed('spool', 'success')
        logger.info("event_spooled", filename=fname.name)
    except Exception as e:
        metrics.record_event_processed('spool', 'failed')
        logger.error(
            "spool_failed",
            error=str(e),
            error_type=type(e).__name__
        )


async def drain_spool() -> None:
    """
    Background task to drain the spool directory.
    
    Continuously attempts to forward spooled events to the Local API.
    Runs every `config.drain_interval_s` seconds.
    """
    logger.info("spool_drainer_started", interval_s=config.drain_interval_s)
    
    while True:
        try:
            files = sorted(SPOOL_DIR.glob('*.json'))
            spool_count = len(files)
            metrics.update_spool_count(spool_count)
            
            if spool_count > 0:
                logger.debug("draining_spool", count=spool_count)
            
            for p in files:
                try:
                    data = json.loads(p.read_text(encoding='utf-8'))
                    await forward(data)
                    p.unlink(missing_ok=True)
                    logger.debug("spool_file_processed", filename=p.name)
                except Exception as e:
                    logger.warning(
                        "spool_drain_item_failed",
                        filename=p.name,
                        error=str(e)
                    )
                    # Keep file for next attempt
            
        except Exception as e:
            logger.error("spool_drain_error", error=str(e))
        
        await asyncio.sleep(config.drain_interval_s)


@app.on_event('startup')
async def start() -> None:
    """Startup handler - start background tasks."""
    logger.info(
        "service_starting",
        local_api_base=config.local_api_base,
        spool_dir=str(SPOOL_DIR),
        drain_interval_s=config.drain_interval_s
    )
    asyncio.create_task(drain_spool())
    logger.info("service_started")


@app.on_event('shutdown')
async def shutdown() -> None:
    """Shutdown handler."""
    logger.info("service_shutting_down")


@app.post('/v1/ingest/events')
async def ingest(ev: IngestEvent) -> JSONResponse:
    """
    Ingest a single event.
    
    Attempts to forward immediately. If forwarding fails, spools the event
    for later retry by the background drainer.
    
    Args:
        ev: Event to ingest
        
    Returns:
        Success response
    """
    try:
        await forward(ev.model_dump())
    except Exception as e:
        logger.warning(
            "forward_failed_spooling",
            idempotency_key=ev.idempotency_key,
            error=str(e)
        )
        spool(ev.model_dump())
    
    return JSONResponse({'ok': True})


@app.post('/v1/ingest/events:batch')
async def ingest_batch(events: List[IngestEvent]) -> JSONResponse:
    """
    Ingest a batch of events.
    
    Attempts to forward each event. Failed events are spooled.
    
    Args:
        events: List of events to ingest
        
    Returns:
        Response with forwarding statistics
    """
    ok = 0
    for ev in events:
        try:
            await forward(ev.model_dump())
            ok += 1
        except Exception:
            spool(ev.model_dump())
    
    logger.info(
        "batch_processed",
        total=len(events),
        forwarded=ok,
        spooled=len(events) - ok
    )
    
    return JSONResponse({
        'ok': True,
        'forwarded': ok,
        'spooled': len(events) - ok
    })


@app.get('/v1/healthz')
async def healthz() -> JSONResponse:
    """Health check endpoint."""
    spool_count = len(list(SPOOL_DIR.glob('*.json')))
    return JSONResponse({
        'status': 'ok',
        'service': config.service_name,
        'version': '2.0.0',
        'spool_count': spool_count,
        'spool_dir': str(SPOOL_DIR)
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
    uvicorn.run(app, host='0.0.0.0', port=8000, log_config=None)
