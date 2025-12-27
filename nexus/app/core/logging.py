"""Structured logging with JSON formatting and trace context injection

This module provides structured logging capabilities with JSON formatting
for better observability and trace context injection for distributed tracing.

Requirements: 22.1, 22.2, 22.4
"""

import logging
import json
import sys
from typing import Any, Dict, Optional
from datetime import datetime
from contextvars import ContextVar

from app.core.config import get_settings


# Context variable for trace ID injection (Requirement 22.1)
trace_context: ContextVar[Optional[str]] = ContextVar("trace_context", default=None)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging (Requirement 22.2)
    
    Formats log records as JSON with consistent field names including:
    - timestamp: ISO 8601 formatted timestamp
    - level: Log level name
    - logger: Logger name
    - message: Log message
    - trace_id: Trace ID from context (if available)
    - Additional fields from extra parameter
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON
        
        Args:
            record: Log record to format
            
        Returns:
            JSON formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Inject trace ID from context (Requirement 22.1)
        trace_id = trace_context.get()
        if trace_id:
            log_data["trace_id"] = trace_id
        
        # Add exception info if present (Requirement 22.3)
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add stack trace if present
        if record.stack_info:
            log_data["stack_info"] = self.formatStack(record.stack_info)
        
        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add any custom attributes
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info",
                "extra_fields"
            ]:
                log_data[key] = value
        
        return json.dumps(log_data)


def setup_logging(log_level: Optional[str] = None) -> None:
    """Configure structured logging for the application (Requirement 22.4)
    
    Sets up JSON formatted logging with trace context injection.
    Log level can be configured via environment variable or parameter.
    
    Args:
        log_level: Optional log level override (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    settings = get_settings()
    
    # Determine log level (Requirement 22.4)
    level_name = log_level or settings.log_level
    level = getattr(logging, level_name.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(JSONFormatter())
    
    root_logger.addHandler(console_handler)
    
    # Set level for third-party loggers to reduce noise
    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("aiormq").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_trace_context(trace_id: str) -> None:
    """Set trace ID in context for log injection (Requirement 22.1)
    
    Args:
        trace_id: Trace ID to inject into logs
    """
    trace_context.set(trace_id)


def clear_trace_context() -> None:
    """Clear trace ID from context"""
    trace_context.set(None)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    trace_id: Optional[str] = None,
    **extra_fields: Any
) -> None:
    """Log message with optional trace context and extra fields
    
    Args:
        logger: Logger instance
        level: Log level (logging.DEBUG, logging.INFO, etc.)
        message: Log message
        trace_id: Optional trace ID (uses context if not provided)
        **extra_fields: Additional fields to include in log
    """
    # Set trace context if provided
    if trace_id:
        old_trace = trace_context.get()
        trace_context.set(trace_id)
    
    # Create log record with extra fields
    logger.log(level, message, extra={"extra_fields": extra_fields})
    
    # Restore old trace context if we changed it
    if trace_id:
        trace_context.set(old_trace)
