"""
Central API - Aggregation service for multiple local sites.

Federates queries across multiple Local API instances.
Provides a unified interface for cross-site monitoring.
"""
import os
import httpx
import time
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, timedelta

# Import shared utilities
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_utils import setup_logging, get_logger, setup_tracing, instrument_fastapi
from shared_utils import MetricsCollector, get_metrics_collector, trace_async
from shared_utils import CentralAPIConfig

# Configuration
config = CentralAPIConfig()

# Parse SITES from environment if not already set
if not config.sites:
    sites_str = os.getenv('SITES', '')
    if sites_str:
        config.sites = dict([pair.split('=') for pair in filter(None, sites_str.split(','))])

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
    title='Central API Wrapper',
    version='2.0.0',
    description='Aggregation service for multiple local monitoring sites'
)

# Instrument with tracing
if config.enable_tracing:
    instrument_fastapi(app)


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


@trace_async("pass_get")
async def pass_get(site: str, path: str, params: dict) -> dict:
    """
    Forward a GET request to a specific site's Local API.
    
    Args:
        site: Site identifier
        path: API path to query
        params: Query parameters
        
    Returns:
        Response from the local site
        
    Raises:
        HTTPException: If site is unknown or request fails
    """
    base = config.sites.get(site)
    if not base:
        logger.warning("unknown_site_requested", site=site)
        raise HTTPException(404, f'Unknown site: {site}')
    
    try:
        logger.debug("forwarding_request", site=site, path=path)
        async with httpx.AsyncClient() as client:
            r = await client.get(
                base + path,
                params=params,
                timeout=config.request_timeout_s
            )
            r.raise_for_status()
            
            logger.info(
                "request_forwarded",
                site=site,
                path=path,
                status_code=r.status_code
            )
            return r.json()
    
    except httpx.HTTPError as e:
        logger.error(
            "forward_failed",
            site=site,
            path=path,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(502, f'Failed to reach site {site}: {str(e)}')


@app.get('/v1/jobs')
@trace_async("get_jobs")
async def jobs(
    site: str = Query(..., description="Site identifier"),
    **params
) -> JSONResponse:
    """
    Query jobs from a specific site.
    
    Args:
        site: Site identifier
        **params: Additional query parameters passed to the local site
        
    Returns:
        Jobs from the specified site
    """
    result = await pass_get(site, '/v1/jobs', params)
    return JSONResponse(result)


@app.get('/v1/subjobs')
@trace_async("get_subjobs")
async def subjobs(
    site: str = Query(..., description="Site identifier"),
    **params
) -> JSONResponse:
    """
    Query subjobs from a specific site.
    
    Args:
        site: Site identifier
        **params: Additional query parameters passed to the local site
        
    Returns:
        Subjobs from the specified site
    """
    result = await pass_get(site, '/v1/subjobs', params)
    return JSONResponse(result)


@app.get('/v1/sites')
async def list_sites() -> JSONResponse:
    """
    List all configured sites.
    
    Returns:
        List of site identifiers and their endpoints
    """
    return JSONResponse({
        'sites': [
            {'id': site_id, 'endpoint': endpoint}
            for site_id, endpoint in config.sites.items()
        ],
        'count': len(config.sites)
    })


@app.get('/v1/healthz')
async def healthz() -> JSONResponse:
    """
    Health check endpoint.
    
    Also checks connectivity to all configured sites.
    """
    site_health = {}
    
    for site_id, base_url in config.sites.items():
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{base_url}/v1/healthz",
                    timeout=2.0
                )
                site_health[site_id] = {
                    'status': 'ok' if r.status_code == 200 else 'degraded',
                    'endpoint': base_url
                }
        except Exception as e:
            site_health[site_id] = {
                'status': 'unreachable',
                'endpoint': base_url,
                'error': str(e)
            }
    
    all_ok = all(s['status'] == 'ok' for s in site_health.values())
    
    return JSONResponse({
        'status': 'ok' if all_ok else 'degraded',
        'service': config.service_name,
        'version': '2.0.0',
        'sites': site_health
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
    logger.info("starting_central_api", sites=config.sites)
    uvicorn.run(app, host='0.0.0.0', port=19000, log_config=None)
