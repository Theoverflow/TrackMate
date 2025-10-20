"""
Enhanced API Gateway with dual endpoints for managed and external data sources.
"""

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import asyncio

from data_adapters import (
    DataAdapter,
    AdapterResult,
    TimescaleDBAdapter,
    S3Adapter,
    ELKAdapter
)

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# ============================================================================
# Configuration and State
# ============================================================================

class AdapterManager:
    """Manages all data adapters (managed and external)."""
    
    def __init__(self):
        self.managed_adapter: Optional[TimescaleDBAdapter] = None
        self.external_adapters: Dict[str, DataAdapter] = {}
    
    async def initialize(self):
        """Initialize all configured adapters."""
        # Initialize managed adapter (TimescaleDB)
        try:
            self.managed_adapter = TimescaleDBAdapter(
                "timescaledb",
                {
                    "connection_string": "postgresql://wafer_user:wafer_pass@localhost:15432/wafer_monitor"
                }
            )
            await self.managed_adapter.initialize()
            logger.info("Managed adapter initialized")
        except Exception as e:
            logger.error("Failed to initialize managed adapter", error=str(e))
        
        # Initialize external adapters (S3, ELK, etc.)
        # TODO: Load from configuration
        external_configs = {
            "s3": {
                "type": "s3",
                "config": {
                    "bucket_name": "monitoring-events",
                    "prefix": "monitoring_events",
                    "region_name": "us-east-1"
                }
            },
            "elk": {
                "type": "elk",
                "config": {
                    "hosts": ["http://localhost:9200"],
                    "index_pattern": "monitoring-events-*"
                }
            }
        }
        
        for name, adapter_cfg in external_configs.items():
            try:
                adapter_type = adapter_cfg["type"]
                config = adapter_cfg["config"]
                
                if adapter_type == "s3":
                    adapter = S3Adapter(name, config)
                elif adapter_type == "elk":
                    adapter = ELKAdapter(name, config)
                else:
                    logger.warning("Unknown adapter type", type=adapter_type, name=name)
                    continue
                
                await adapter.initialize()
                self.external_adapters[name] = adapter
                logger.info("External adapter initialized", name=name, type=adapter_type)
            except Exception as e:
                logger.error("Failed to initialize external adapter", name=name, error=str(e))
    
    async def close(self):
        """Close all adapters."""
        if self.managed_adapter:
            await self.managed_adapter.close()
        
        for adapter in self.external_adapters.values():
            await adapter.close()
        
        logger.info("All adapters closed")

# Global adapter manager
adapter_manager = AdapterManager()

# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting API Gateway...")
    await adapter_manager.initialize()
    logger.info("API Gateway ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API Gateway...")
    await adapter_manager.close()
    logger.info("API Gateway stopped")

# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Wafer Monitor API Gateway",
    description="Unified API for querying monitoring data from managed and external sources",
    version="0.3.0",
    lifespan=lifespan
)

# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for event queries."""
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply (site_id, app_name, etc.)")
    start_time: Optional[datetime] = Field(None, description="Start of time range")
    end_time: Optional[datetime] = Field(None, description="End of time range")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of events to return")
    offset: int = Field(0, ge=0, description="Number of events to skip")

class QueryResponse(BaseModel):
    """Response model for event queries."""
    success: bool
    source: str
    count: int
    events: List[Dict[str, Any]]
    query_time_ms: float
    error: Optional[str] = None

class UnifiedQueryResponse(BaseModel):
    """Response model for unified queries across all sources."""
    success: bool
    sources: List[str]
    total_count: int
    events: List[Dict[str, Any]]
    query_time_ms: float
    source_results: Dict[str, QueryResponse]

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    adapters: Dict[str, Dict[str, Any]]

# ============================================================================
# Endpoint 1: Managed Data Source (TimescaleDB)
# ============================================================================

@app.get("/v1/managed/health", response_model=Dict[str, Any])
async def managed_health():
    """Health check for the managed data source."""
    if not adapter_manager.managed_adapter:
        return {"status": "error", "message": "Managed adapter not initialized"}
    
    is_healthy = await adapter_manager.managed_adapter.health_check()
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "adapter": "timescaledb",
        "message": "Managed data source status"
    }

@app.post("/v1/managed/events/query", response_model=QueryResponse)
async def query_managed_events(request: QueryRequest):
    """
    Query events from the managed TimescaleDB data source.
    
    This endpoint queries events that were sent via the sidecar agent
    to the Local API and stored in the managed TimescaleDB instance.
    """
    if not adapter_manager.managed_adapter:
        raise HTTPException(status_code=503, detail="Managed adapter not available")
    
    result = await adapter_manager.managed_adapter.query_events(
        filters=request.filters,
        start_time=request.start_time,
        end_time=request.end_time,
        limit=request.limit,
        offset=request.offset
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Query failed")
    
    return QueryResponse(
        success=result.success,
        source=result.source,
        count=result.count,
        events=result.data,
        query_time_ms=result.query_time_ms
    )

# ============================================================================
# Endpoint 2: External Data Sources (S3, ELK, etc.)
# ============================================================================

@app.get("/v1/external/sources", response_model=Dict[str, List[str]])
async def list_external_sources():
    """List available external data sources."""
    return {
        "sources": list(adapter_manager.external_adapters.keys())
    }

@app.get("/v1/external/health/{source_name}", response_model=Dict[str, Any])
async def external_source_health(source_name: str):
    """Health check for a specific external data source."""
    adapter = adapter_manager.external_adapters.get(source_name)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
    
    is_healthy = await adapter.health_check()
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "source": source_name,
        "adapter_type": adapter.get_source_name()
    }

@app.post("/v1/external/events/query/{source_name}", response_model=QueryResponse)
async def query_external_events(source_name: str, request: QueryRequest):
    """
    Query events from a specific external data source (S3, ELK, etc.).
    
    This endpoint queries events that were written directly to external
    systems (S3, Elasticsearch) without going through the managed database.
    """
    adapter = adapter_manager.external_adapters.get(source_name)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
    
    result = await adapter.query_events(
        filters=request.filters,
        start_time=request.start_time,
        end_time=request.end_time,
        limit=request.limit,
        offset=request.offset
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Query failed")
    
    return QueryResponse(
        success=result.success,
        source=result.source,
        count=result.count,
        events=result.data,
        query_time_ms=result.query_time_ms
    )

# ============================================================================
# Endpoint 3: Unified Query (All Sources)
# ============================================================================

@app.post("/v1/unified/events/query", response_model=UnifiedQueryResponse)
async def query_unified_events(request: QueryRequest):
    """
    Query events from all available sources (managed + external) and merge results.
    
    This endpoint queries both the managed TimescaleDB and all configured external
    sources concurrently, then merges and sorts the results by timestamp.
    """
    import time
    start = time.time()
    
    # Query all sources concurrently
    tasks = []
    source_names = []
    
    # Add managed source
    if adapter_manager.managed_adapter:
        tasks.append(adapter_manager.managed_adapter.query_events(
            filters=request.filters,
            start_time=request.start_time,
            end_time=request.end_time,
            limit=request.limit,
            offset=request.offset
        ))
        source_names.append("managed")
    
    # Add external sources
    for name, adapter in adapter_manager.external_adapters.items():
        tasks.append(adapter.query_events(
            filters=request.filters,
            start_time=request.start_time,
            end_time=request.end_time,
            limit=request.limit,
            offset=request.offset
        ))
        source_names.append(name)
    
    # Execute queries concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    all_events = []
    source_results = {}
    successful_sources = []
    
    for i, result in enumerate(results):
        source_name = source_names[i]
        
        if isinstance(result, Exception):
            logger.error("Query failed for source", source=source_name, error=str(result))
            source_results[source_name] = QueryResponse(
                success=False,
                source=source_name,
                count=0,
                events=[],
                query_time_ms=0,
                error=str(result)
            )
        else:
            source_results[source_name] = QueryResponse(
                success=result.success,
                source=result.source,
                count=result.count,
                events=result.data,
                query_time_ms=result.query_time_ms,
                error=result.error
            )
            
            if result.success:
                # Add source information to each event
                for event in result.data:
                    event['_source'] = source_name
                all_events.extend(result.data)
                successful_sources.append(source_name)
    
    # Sort by timestamp (most recent first)
    all_events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    
    # Apply limit across all sources
    paginated_events = all_events[:request.limit]
    
    query_time = (time.time() - start) * 1000
    
    logger.info("Unified query completed",
                sources=len(successful_sources),
                total_events=len(all_events),
                returned_events=len(paginated_events),
                query_time_ms=query_time)
    
    return UnifiedQueryResponse(
        success=len(successful_sources) > 0,
        sources=successful_sources,
        total_count=len(paginated_events),
        events=paginated_events,
        query_time_ms=query_time,
        source_results=source_results
    )

# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Overall health check for all adapters."""
    adapters_status = {}
    
    # Check managed adapter
    if adapter_manager.managed_adapter:
        is_healthy = await adapter_manager.managed_adapter.health_check()
        adapters_status["managed"] = {
            "type": "timescaledb",
            "status": "healthy" if is_healthy else "unhealthy"
        }
    
    # Check external adapters
    for name, adapter in adapter_manager.external_adapters.items():
        is_healthy = await adapter.health_check()
        adapters_status[name] = {
            "type": adapter.get_source_name(),
            "status": "healthy" if is_healthy else "unhealthy"
        }
    
    # Determine overall status
    all_healthy = all(a["status"] == "healthy" for a in adapters_status.values())
    overall_status = "healthy" if all_healthy else "degraded"
    
    return HealthResponse(
        status=overall_status,
        adapters=adapters_status
    )

@app.get("/info")
async def api_info():
    """API information and capabilities."""
    return {
        "name": "Wafer Monitor API Gateway",
        "version": "0.3.0",
        "description": "Unified API for querying monitoring data",
        "endpoints": {
            "managed": "/v1/managed/events/query",
            "external": "/v1/external/events/query/{source}",
            "unified": "/v1/unified/events/query"
        },
        "features": [
            "Dual data source support (managed + external)",
            "Concurrent multi-source queries",
            "Time-range filtering",
            "Field-based filtering",
            "Pagination support"
        ],
        "managed_adapter": "timescaledb" if adapter_manager.managed_adapter else None,
        "external_adapters": list(adapter_manager.external_adapters.keys())
    }

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18001, log_level="info")

