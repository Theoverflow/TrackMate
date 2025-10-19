"""Configuration management with validation."""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceConfig(BaseSettings):
    """Base configuration for all services."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Service info
    service_name: str = Field(default="unknown", description="Service name")
    service_version: str = Field(default="0.2.0", description="Service version")
    environment: str = Field(default="development", description="Environment (development/staging/production)")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    json_logs: bool = Field(default=True, description="Output logs as JSON")
    
    # Tracing
    enable_tracing: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    otlp_endpoint: Optional[str] = Field(default=None, description="OTLP collector endpoint")
    
    # Metrics
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")


class SidecarAgentConfig(BaseServiceConfig):
    """Configuration for Sidecar Agent."""
    
    service_name: str = "sidecar-agent"
    
    local_api_base: str = Field(default="http://localhost:18000", description="Local API base URL")
    spool_dir: str = Field(default="/tmp/sidecar-spool", description="Spool directory for failed events")
    drain_interval_s: float = Field(default=2.0, description="Spool drain interval in seconds")
    request_timeout_s: float = Field(default=5.0, description="HTTP request timeout")
    max_batch_size: int = Field(default=100, description="Maximum batch size for event forwarding")


class LocalAPIConfig(BaseServiceConfig):
    """Configuration for Local API."""
    
    service_name: str = "local-api"
    
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/monitor", description="PostgreSQL connection URL")
    db_pool_min_size: int = Field(default=2, description="Minimum database pool size")
    db_pool_max_size: int = Field(default=10, description="Maximum database pool size")
    max_skew_s: int = Field(default=600, description="Maximum allowed event time skew in seconds")
    query_default_limit: int = Field(default=1000, description="Default query result limit")
    query_max_limit: int = Field(default=10000, description="Maximum query result limit")


class CentralAPIConfig(BaseServiceConfig):
    """Configuration for Central API."""
    
    service_name: str = "central-api"
    
    sites: dict[str, str] = Field(default_factory=dict, description="Site ID to Local API URL mapping")
    request_timeout_s: float = Field(default=3.0, description="HTTP request timeout")
    cache_ttl_s: int = Field(default=30, description="Cache TTL in seconds")


class ArchiverConfig(BaseServiceConfig):
    """Configuration for Archiver."""
    
    service_name: str = "archiver"
    
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/monitor", description="PostgreSQL connection URL")
    s3_bucket: str = Field(default="my-bucket", description="S3 bucket name")
    s3_prefix: str = Field(default="monitoring/", description="S3 key prefix")
    site_id: str = Field(default="unknown", description="Site identifier")
    archive_interval_hours: int = Field(default=1, description="Archive interval in hours")
    retention_hours: int = Field(default=72, description="Data retention in hot storage (hours)")

