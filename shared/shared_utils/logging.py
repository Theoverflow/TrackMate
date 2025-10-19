"""Structured logging setup with structlog."""
import sys
import logging
from typing import Any
import structlog
from structlog.typing import EventDict, Processor


def add_service_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add service context to all log entries."""
    import os
    event_dict["service"] = os.getenv("SERVICE_NAME", "unknown")
    event_dict["environment"] = os.getenv("ENVIRONMENT", "development")
    return event_dict


def setup_logging(service_name: str, level: str = "INFO", json_logs: bool = True) -> None:
    """
    Setup structured logging with structlog.
    
    Args:
        service_name: Name of the service for logging context
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output logs as JSON (True) or human-readable (False)
    """
    import os
    os.environ["SERVICE_NAME"] = service_name
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    
    # Configure structlog processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_service_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    
    if json_logs:
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ])
    else:
        processors.extend([
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.dev.ConsoleRenderer()
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)

