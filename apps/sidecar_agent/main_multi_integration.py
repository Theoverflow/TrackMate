"""
Sidecar Agent with Multi-Integration Support and Dependency Injection.

Enhanced version that supports multiple backends simultaneously:
- Local API (TimescaleDB)
- Zabbix monitoring
- ELK stack (Elasticsearch)
- CSV export
- JSON export  
- Custom webhooks
"""
import os
import asyncio
import json
import uuid
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import time

# Import shared utilities
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_utils import setup_logging, get_logger
from shared_utils import MetricsCollector, get_metrics_collector
from shared_utils import SidecarAgentConfig
from shared_utils.integrations import IntegrationContainer, get_container, IntegrationConfig, IntegrationType

# Configuration
config = SidecarAgentConfig()

# Setup observability
setup_logging(config.service_name, level=config.log_level, json_logs=config.json_logs)
logger = get_logger(__name__)

# Initialize metrics collector
metrics = get_metrics_collector(config.service_name)

# Setup directories
SPOOL_DIR = Path(config.spool_dir)
SPOOL_DIR.mkdir(parents=True, exist_ok=True)

# FastAPI app
app = FastAPI(
    title='Sidecar Agent (Multi-Integration)',
    version='3.0.0',
    description='Event forwarding service with multiple integration backends'
)

# Integration container (dependency injection)
container: IntegrationContainer = get_container()


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


async def forward(ev: dict) -> Dict[str, bool]:
    """
    Forward an event to all enabled integrations.
    
    Args:
        ev: Event dict to forward
        
    Returns:
        Dictionary mapping integration name to success status
    """
    logger.debug("forwarding_event_to_integrations", event_kind=ev.get('event', {}).get('kind'))
    
    results = await container.send_event(ev)
    
    # Record metrics for each integration
    for integration_name, success in results.items():
        status = 'success' if success else 'failed'
        metrics.record_event_processed(f'forward_{integration_name}', status)
    
    # Log results
    successful = [name for name, success in results.items() if success]
    failed = [name for name, success in results.items() if not success]
    
    if successful:
        logger.info(
            "event_forwarded",
            event_kind=ev.get('event', {}).get('kind'),
            successful_integrations=successful
        )
    
    if failed:
        logger.warning(
            "event_forward_partial_failure",
            event_kind=ev.get('event', {}).get('kind'),
            failed_integrations=failed
        )
    
    return results


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
    
    Continuously attempts to forward spooled events to all integrations.
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
                    results = await forward(data)
                    
                    # Only remove file if at least one integration succeeded
                    if any(results.values()):
                        p.unlink(missing_ok=True)
                        logger.debug("spool_file_processed", filename=p.name)
                    else:
                        logger.warning(
                            "spool_file_forward_all_failed",
                            filename=p.name
                        )
                except Exception as e:
                    logger.warning(
                        "spool_drain_item_failed",
                        filename=p.name,
                        error=str(e)
                    )
            
        except Exception as e:
            logger.error("spool_drain_error", error=str(e))
        
        await asyncio.sleep(config.drain_interval_s)


@app.on_event('startup')
async def start() -> None:
    """Startup handler - initialize integrations and start background tasks."""
    logger.info(
        "service_starting",
        spool_dir=str(SPOOL_DIR),
        drain_interval_s=config.drain_interval_s
    )
    
    # Load integrations from environment
    container.register_from_env()
    
    # Initialize all integrations
    await container.initialize_all()
    
    # Log active integrations
    enabled = container.get_enabled_integrations()
    logger.info(
        "integrations_loaded",
        count=len(enabled),
        integrations=enabled
    )
    
    # Start spool drainer
    asyncio.create_task(drain_spool())
    
    logger.info("service_started")


@app.on_event('shutdown')
async def shutdown() -> None:
    """Shutdown handler - close all integrations."""
    logger.info("service_shutting_down")
    await container.close_all()
    logger.info("service_shutdown_complete")


@app.post('/v1/ingest/events')
async def ingest(ev: IngestEvent) -> JSONResponse:
    """
    Ingest a single event.
    
    Attempts to forward immediately to all enabled integrations.
    If all fail, spools the event for later retry.
    
    Args:
        ev: Event to ingest
        
    Returns:
        Success response with forwarding details
    """
    results = await forward(ev.model_dump())
    
    # If all integrations failed, spool the event
    if not any(results.values()):
        logger.warning(
            "all_integrations_failed_spooling",
            idempotency_key=ev.idempotency_key
        )
        spool(ev.model_dump())
    
    return JSONResponse({
        'ok': True,
        'integrations': results
    })


@app.post('/v1/ingest/events:batch')
async def ingest_batch(events: List[IngestEvent]) -> JSONResponse:
    """
    Ingest a batch of events.
    
    Forwards batch to all enabled integrations. Failed events are spooled.
    
    Args:
        events: List of events to ingest
        
    Returns:
        Response with batch forwarding statistics
    """
    event_dicts = [ev.model_dump() for ev in events]
    results = await container.send_batch(event_dicts)
    
    # Spool events that failed on all integrations
    for i, ev in enumerate(events):
        all_failed = all(
            result.get('failed', 0) > 0 
            for result in results.values()
        )
        if all_failed:
            spool(ev.model_dump())
    
    logger.info(
        "batch_processed",
        total=len(events),
        integration_results=results
    )
    
    return JSONResponse({
        'ok': True,
        'total': len(events),
        'integration_results': results
    })


@app.get('/v1/healthz')
async def healthz() -> JSONResponse:
    """Health check endpoint with integration status."""
    spool_count = len(list(SPOOL_DIR.glob('*.json')))
    
    # Check health of all integrations
    integration_health = await container.health_check_all()
    
    # Determine overall status
    all_healthy = all(
        h.get('status') == 'healthy' 
        for h in integration_health.values()
    )
    
    return JSONResponse({
        'status': 'ok' if all_healthy else 'degraded',
        'service': config.service_name,
        'version': '3.0.0',
        'spool_count': spool_count,
        'spool_dir': str(SPOOL_DIR),
        'integrations': integration_health
    })


@app.get('/v1/integrations')
async def list_integrations() -> JSONResponse:
    """List all configured integrations."""
    enabled = container.get_enabled_integrations()
    all_integrations = container.list_integrations()
    
    return JSONResponse({
        'total': len(all_integrations),
        'enabled': len(enabled),
        'integrations': all_integrations,
        'enabled_integrations': enabled
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

