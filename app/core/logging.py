"""Structured logging configuration for production-grade observability.

Provides JSON-formatted logs with context tracking, request IDs, and integration
with cloud logging services (Stackdriver, CloudWatch, etc.).
"""
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import traceback


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging.
    
    Outputs logs in JSON format for easy parsing by log aggregation services.
    Includes timestamp, level, message, module, function, and custom fields.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.
        
        Args:
            record: LogRecord to format
            
        Returns:
            JSON string with log data
        """
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add custom fields from 'extra' parameter
        if hasattr(record, 'extra_fields'):
            log_obj.update(record.extra_fields)
        
        # Add request context if available
        for attr in ['request_id', 'user_id', 'session_id', 'endpoint', 'method', 
                     'status_code', 'duration_ms', 'error_type']:
            if hasattr(record, attr):
                log_obj[attr] = getattr(record, attr)
        
        return json.dumps(log_obj, default=str)


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that includes context in all log messages.
    
    Allows setting persistent context (request_id, user_id, etc.) that
    automatically gets included in all log messages.
    
    Example:
        >>> logger = ContextLogger(base_logger, {"request_id": "abc123"})
        >>> logger.info("Processing request")
        # Output includes request_id automatically
    """
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message and add context.
        
        Args:
            msg: Log message
            kwargs: Additional keyword arguments
            
        Returns:
            Tuple of (message, kwargs) with context added
        """
        # Merge context into extra fields
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    include_timestamp: bool = True
) -> logging.Logger:
    """Configure application-wide logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Whether to use JSON formatter (True for production)
        include_timestamp: Whether to include timestamps in console output
        
    Returns:
        Configured root logger
        
    Example:
        >>> logger = setup_logging(level="INFO", json_format=True)
        >>> logger.info("Application started")
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # Set formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        # Human-readable format for development
        fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(fmt)
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    return root_logger


def get_logger(name: str, context: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """Get a logger with optional context.
    
    Args:
        name: Logger name (typically __name__ of module)
        context: Optional context dict to include in all logs
        
    Returns:
        Logger or ContextLogger if context provided
        
    Example:
        >>> logger = get_logger(__name__, {"service": "api"})
        >>> logger.info("Request processed", extra={"duration_ms": 245})
    """
    logger = logging.getLogger(name)
    
    if context:
        return ContextLogger(logger, context)
    
    return logger


# Convenience function for timing operations
class LogTimer:
    """Context manager for timing operations and logging duration.
    
    Example:
        >>> logger = get_logger(__name__)
        >>> with LogTimer(logger, "database_query"):
        ...     result = db.query(...)
        # Logs: "database_query completed in 125ms"
    """
    
    def __init__(self, logger: logging.Logger, operation: str):
        """Initialize timer.
        
        Args:
            logger: Logger to use
            operation: Name of operation being timed
        """
        self.logger = logger
        self.operation = operation
        self.start_time: Optional[datetime] = None
    
    def __enter__(self):
        """Start timer."""
        self.start_time = datetime.utcnow()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timer and log duration."""
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds() * 1000
            
            if exc_type:
                self.logger.error(
                    f"{self.operation} failed after {duration:.1f}ms",
                    extra={"operation": self.operation, "duration_ms": duration},
                    exc_info=True
                )
            else:
                self.logger.info(
                    f"{self.operation} completed in {duration:.1f}ms",
                    extra={"operation": self.operation, "duration_ms": duration}
                )


# Initialize logging on module import (can be reconfigured later)
setup_logging(
    level="INFO",
    json_format=False  # Set to True for production JSON logs
)
