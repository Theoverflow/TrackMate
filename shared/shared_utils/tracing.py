"""OpenTelemetry distributed tracing setup."""
import os
import functools
from typing import Any, Callable, TypeVar, ParamSpec
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

P = ParamSpec('P')
R = TypeVar('R')


def setup_tracing(service_name: str, otlp_endpoint: str | None = None) -> trace.Tracer:
    """
    Setup OpenTelemetry tracing.
    
    Args:
        service_name: Name of the service for tracing context
        otlp_endpoint: Optional OTLP collector endpoint (e.g., "http://localhost:4317")
                      If not provided, uses OTEL_EXPORTER_OTLP_ENDPOINT env var
    
    Returns:
        Configured tracer instance
    """
    # Create resource with service name
    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.getenv("SERVICE_VERSION", "0.2.0"),
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Configure exporters
    otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    
    if otlp_endpoint:
        # Export to OTLP collector (e.g., Jaeger, Tempo, etc.)
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    else:
        # Fallback to console for development
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
    
    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    
    # Instrument HTTP clients
    HTTPXClientInstrumentor().instrument()
    
    return trace.get_tracer(service_name)


def instrument_fastapi(app: Any) -> None:
    """Instrument a FastAPI application with tracing."""
    FastAPIInstrumentor.instrument_app(app)


def trace_async(span_name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to trace async functions.
    
    Args:
        span_name: Optional custom span name (defaults to function name)
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        tracer = trace.get_tracer(__name__)
        name = span_name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with tracer.start_as_current_span(name) as span:
                try:
                    span.set_attribute("function", func.__name__)
                    result = await func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise
        
        return wrapper  # type: ignore
    return decorator


def trace_sync(span_name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to trace synchronous functions.
    
    Args:
        span_name: Optional custom span name (defaults to function name)
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        tracer = trace.get_tracer(__name__)
        name = span_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with tracer.start_as_current_span(name) as span:
                try:
                    span.set_attribute("function", func.__name__)
                    result = func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator

