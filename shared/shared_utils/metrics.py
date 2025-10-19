"""Prometheus metrics collection."""
import time
from typing import Dict, Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST


class MetricsCollector:
    """Centralized metrics collector using Prometheus client."""
    
    def __init__(self, service_name: str, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.
        
        Args:
            service_name: Name of the service for metrics labeling
            registry: Optional custom registry (defaults to default registry)
        """
        self.service_name = service_name
        self.registry = registry or CollectorRegistry()
        
        # HTTP request metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request latency',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # Database metrics
        self.db_operations_total = Counter(
            'db_operations_total',
            'Total database operations',
            ['operation', 'table', 'status'],
            registry=self.registry
        )
        
        self.db_operation_duration_seconds = Histogram(
            'db_operation_duration_seconds',
            'Database operation latency',
            ['operation', 'table'],
            registry=self.registry
        )
        
        self.db_pool_size = Gauge(
            'db_pool_size',
            'Current database connection pool size',
            registry=self.registry
        )
        
        self.db_pool_available = Gauge(
            'db_pool_available',
            'Available database connections',
            registry=self.registry
        )
        
        # Event processing metrics
        self.events_processed_total = Counter(
            'events_processed_total',
            'Total events processed',
            ['event_type', 'status'],
            registry=self.registry
        )
        
        self.events_in_spool = Gauge(
            'events_in_spool',
            'Number of events in spool directory',
            registry=self.registry
        )
        
        # Job metrics
        self.jobs_total = Counter(
            'jobs_total',
            'Total jobs',
            ['app_name', 'status'],
            registry=self.registry
        )
        
        self.job_duration_seconds = Histogram(
            'job_duration_seconds',
            'Job duration',
            ['app_name'],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
            registry=self.registry
        )
        
        # System metrics
        self.system_cpu_usage = Gauge(
            'system_cpu_usage',
            'System CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_usage_bytes = Gauge(
            'system_memory_usage_bytes',
            'System memory usage in bytes',
            registry=self.registry
        )
    
    def record_http_request(self, method: str, endpoint: str, status: int, duration: float) -> None:
        """Record HTTP request metrics."""
        self.http_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        self.http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
    
    def record_db_operation(self, operation: str, table: str, status: str, duration: float) -> None:
        """Record database operation metrics."""
        self.db_operations_total.labels(operation=operation, table=table, status=status).inc()
        self.db_operation_duration_seconds.labels(operation=operation, table=table).observe(duration)
    
    def record_event_processed(self, event_type: str, status: str) -> None:
        """Record event processing metrics."""
        self.events_processed_total.labels(event_type=event_type, status=status).inc()
    
    def record_job(self, app_name: str, status: str, duration: Optional[float] = None) -> None:
        """Record job metrics."""
        self.jobs_total.labels(app_name=app_name, status=status).inc()
        if duration is not None:
            self.job_duration_seconds.labels(app_name=app_name).observe(duration)
    
    def update_pool_metrics(self, size: int, available: int) -> None:
        """Update database pool metrics."""
        self.db_pool_size.set(size)
        self.db_pool_available.set(available)
    
    def update_spool_count(self, count: int) -> None:
        """Update spool directory count."""
        self.events_in_spool.set(count)
    
    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry)
    
    def get_content_type(self) -> str:
        """Get content type for metrics endpoint."""
        return CONTENT_TYPE_LATEST


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector(service_name: str | None = None) -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        if service_name is None:
            raise ValueError("service_name must be provided on first call")
        _metrics_collector = MetricsCollector(service_name)
    return _metrics_collector

