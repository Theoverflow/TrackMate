"""
Enhanced Sidecar Agent with Multi-Backend Support.

This is the new sidecar implementation with pluggable backend routing.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from .backend_router import (
    BackendRouter,
    BackendRegistry,
    BackendConfig,
    BackendType,
    load_config
)
from .backends.managed_api import ManagedAPIBackend

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)


# Register available backends
BackendRegistry.register(BackendType.MANAGED_API, ManagedAPIBackend)

# TODO: Register other backends (FS, S3, ELK, etc.)

# FastAPI app
app = FastAPI(
    title="Sidecar Agent (Enhanced)",
    description="Multi-backend event routing agent",
    version="0.3.0"
)

# Global router instance
router: BackendRouter = None


class Event(BaseModel):
    """Single event model."""
    idempotency_key: str
    site_id: str
    app: Dict[str, Any]
    entity: Dict[str, Any]
    event: Dict[str, Any]


class EventBatch(BaseModel):
    """Batch of events model."""
    events: List[Dict[str, Any]]


@app.on_event("startup")
async def startup():
    """Initialize sidecar on startup."""
    global router
    
    logger.info("sidecar_starting")
    
    # Load backend configuration
    config_path = Path("/etc/sidecar/config.yaml")
    if not config_path.exists():
        # Use default configuration
        logger.warning("config_not_found", path=str(config_path))
        backend_configs = [
            BackendConfig(
                type=BackendType.MANAGED_API,
                enabled=True,
                priority=1,
                config={
                    'url': 'http://localhost:18000',
                    'endpoint': '/v1/ingest/managed'
                }
            )
        ]
    else:
        backend_configs = load_config(config_path)
    
    # Create backend instances
    backends = []
    for config in backend_configs:
        try:
            backend = BackendRegistry.create(config)
            backends.append(backend)
            logger.info(
                "backend_created",
                type=config.type.value,
                priority=config.priority
            )
        except Exception as e:
            logger.error(
                "backend_creation_failed",
                type=config.type.value,
                error=str(e)
            )
    
    # Initialize router
    router = BackendRouter(backends)
    await router.initialize()
    
    logger.info("sidecar_started", backends=len(backends))


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global router
    
    if router:
        await router.close()
    
    logger.info("sidecar_stopped")


@app.post("/v1/ingest/events")
async def ingest_event(event: Event):
    """
    Ingest a single event and route to backends.
    
    Args:
        event: Event to ingest
        
    Returns:
        Status and backend results
    """
    if router is None:
        raise HTTPException(status_code=503, detail="Router not initialized")
    
    try:
        event_dict = event.dict()
        results = await router.route_event(event_dict)
        
        # Check if at least one backend succeeded
        success_count = sum(1 for r in results.values() if r.success)
        
        if success_count == 0:
            logger.error("all_backends_failed", event_id=event.idempotency_key)
            raise HTTPException(
                status_code=500,
                detail="All backends failed to process event"
            )
        
        return {
            "status": "ok",
            "backends": {
                name: {
                    "success": result.success,
                    "latency_ms": result.latency_ms,
                    "error": result.error
                }
                for name, result in results.items()
            }
        }
    
    except Exception as e:
        logger.error("event_ingestion_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/ingest/batch")
async def ingest_batch(batch: EventBatch):
    """
    Ingest a batch of events and route to backends.
    
    Args:
        batch: Batch of events
        
    Returns:
        Status and backend results
    """
    if router is None:
        raise HTTPException(status_code=503, detail="Router not initialized")
    
    try:
        results = await router.route_batch(batch.events)
        
        # Check if at least one backend succeeded
        success_count = sum(1 for r in results.values() if r.success)
        
        if success_count == 0:
            logger.error("all_backends_failed_batch", count=len(batch.events))
            raise HTTPException(
                status_code=500,
                detail="All backends failed to process batch"
            )
        
        return {
            "status": "ok",
            "count": len(batch.events),
            "backends": {
                name: {
                    "success": result.success,
                    "events_sent": result.events_sent,
                    "events_failed": result.events_failed,
                    "latency_ms": result.latency_ms,
                    "error": result.error
                }
                for name, result in results.items()
            }
        }
    
    except Exception as e:
        logger.error("batch_ingestion_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """
    Health check endpoint.
    
    Returns health status of sidecar and all backends.
    """
    if router is None:
        return {"status": "starting"}
    
    backend_health = await router.health_check()
    router_status = router.get_status()
    
    all_healthy = all(h["healthy"] for h in backend_health.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "router": router_status,
        "backends": backend_health
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics for monitoring.
    """
    if router is None:
        return {"status": "not_initialized"}
    
    status = router.get_status()
    
    # TODO: Return Prometheus-format metrics
    return {
        "backends_total": status["backends_total"],
        "backends_healthy": status["backends_healthy"],
        "backends_degraded": status["backends_degraded"],
        "backends_failed": status["backends_failed"]
    }


def main():
    """Run the sidecar agent."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=17000,
        log_level="info"
    )


if __name__ == "__main__":
    main()

