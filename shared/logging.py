"""
Logging infrastructure for Holiday Meal Planner.

Provides structured logging with correlation IDs for debugging multi-agent
pipeline operations and request tracing.
"""

import logging
import logging.config
import sys
import json
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional, List
from datetime import datetime

from .config import get_settings


# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')


class CorrelationFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to the log record."""
        record.correlation_id = get_correlation_id()
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, include_fields: Optional[List[str]] = None):
        """
        Initialize JSON formatter.

        Args:
            include_fields: List of additional fields to include
        """
        super().__init__()
        self.include_fields = include_fields or []

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, 'correlation_id', ''),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add any additional fields
        for field in self.include_fields:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)

        # Add extra fields from the record
        for key, value in record.__dict__.items():
            if key not in log_entry and not key.startswith('_'):
                try:
                    # Ensure value is JSON serializable
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        return json.dumps(log_entry)


class PerformanceFilter(logging.Filter):
    """Filter for performance-related logging."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow performance-related records."""
        return hasattr(record, 'performance') and record.performance


def get_correlation_id() -> str:
    """Get current correlation ID from context."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID in context.

    Args:
        correlation_id: Specific correlation ID or None to generate

    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())[:8]  # Short UUID

    correlation_id_var.set(correlation_id)
    return correlation_id


def clear_correlation_id() -> None:
    """Clear correlation ID from context."""
    correlation_id_var.set('')


def setup_logging(
    log_level: Optional[str] = None,
    json_format: bool = False,
    enable_performance_logging: bool = True,
) -> None:
    """
    Setup application logging configuration.

    Args:
        log_level: Override log level
        json_format: Use JSON formatter
        enable_performance_logging: Enable performance metrics logging
    """
    settings = get_settings()
    level = log_level or settings.log_level

    # Create formatters
    if json_format:
        formatter = JSONFormatter(include_fields=['agent_name', 'task_id', 'processing_time'])
    else:
        formatter = logging.Formatter(
            fmt=settings.log_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(CorrelationFilter())
    root_logger.addHandler(console_handler)

    # Performance logging handler (if enabled)
    if enable_performance_logging:
        perf_logger = logging.getLogger('performance')
        perf_handler = logging.StreamHandler(sys.stdout)
        perf_handler.setFormatter(JSONFormatter(['processing_time', 'agent_name', 'task_id']))
        perf_handler.addFilter(CorrelationFilter())
        perf_handler.addFilter(PerformanceFilter())
        perf_logger.addHandler(perf_handler)
        perf_logger.setLevel(logging.INFO)
        perf_logger.propagate = False

    # Configure third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)

    # Enable detailed request logging if configured
    if settings.enable_request_logging:
        logging.getLogger('httpx').setLevel(logging.INFO)
        logging.getLogger('requests').setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with correlation ID support.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Add correlation filter if not already present
        if not any(isinstance(f, CorrelationFilter) for f in logger.filters):
            logger.addFilter(CorrelationFilter())
    return logger


# Performance logging utilities

class PerformanceTimer:
    """Context manager for performance timing with automatic logging."""

    def __init__(
        self,
        operation: str,
        logger: Optional[logging.Logger] = None,
        agent_name: Optional[str] = None,
        task_id: Optional[str] = None,
        log_threshold_ms: Optional[int] = None,
    ):
        """
        Initialize performance timer.

        Args:
            operation: Description of operation being timed
            logger: Logger to use (defaults to performance logger)
            agent_name: Name of agent performing operation
            task_id: Task ID being processed
            log_threshold_ms: Only log if time exceeds threshold
        """
        self.operation = operation
        self.logger = logger or logging.getLogger('performance')
        self.agent_name = agent_name
        self.task_id = task_id
        self.log_threshold_ms = log_threshold_ms
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def __enter__(self) -> 'PerformanceTimer':
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End timing and log if threshold met."""
        self.end_time = time.time()

        if self.start_time is not None:
            duration_ms = int((self.end_time - self.start_time) * 1000)

            # Check threshold
            if self.log_threshold_ms is None or duration_ms >= self.log_threshold_ms:
                self._log_performance(duration_ms, exc_type is not None)

    def _log_performance(self, duration_ms: int, has_error: bool) -> None:
        """Log performance metrics."""
        extra = {
            'performance': True,
            'operation': self.operation,
            'processing_time': duration_ms,
            'status': 'error' if has_error else 'success',
        }

        if self.agent_name:
            extra['agent_name'] = self.agent_name

        if self.task_id:
            extra['task_id'] = self.task_id

        message = f"{self.operation} completed in {duration_ms}ms"
        if has_error:
            message += " (with errors)"

        self.logger.info(message, extra=extra)

    def get_duration_ms(self) -> Optional[int]:
        """Get duration in milliseconds if timing is complete."""
        if self.start_time is not None and self.end_time is not None:
            return int((self.end_time - self.start_time) * 1000)
        return None


def log_agent_operation(
    operation: str,
    agent_name: str,
    task_id: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
    **extra_fields,
) -> None:
    """
    Log an agent operation with structured data.

    Args:
        operation: Description of the operation
        agent_name: Name of the agent
        task_id: Task ID being processed
        logger: Logger to use
        **extra_fields: Additional fields to log
    """
    if logger is None:
        logger = get_logger(f'agent.{agent_name}')

    extra = {
        'agent_name': agent_name,
        'operation': operation,
    }

    if task_id:
        extra['task_id'] = task_id

    extra.update(extra_fields)

    logger.info(f"Agent {agent_name}: {operation}", extra=extra)


def log_processing_metrics(
    metrics: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Log processing metrics.

    Args:
        metrics: Dictionary of metrics to log
        logger: Logger to use
    """
    if logger is None:
        logger = logging.getLogger('performance')

    extra = {'performance': True}
    extra.update(metrics)

    logger.info("Processing metrics", extra=extra)


# Request/Response logging utilities

def log_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Log outgoing HTTP request.

    Args:
        method: HTTP method
        url: Request URL
        headers: Request headers (sensitive headers will be masked)
        logger: Logger to use
    """
    if logger is None:
        logger = get_logger('http.request')

    # Mask sensitive headers
    safe_headers = {}
    if headers:
        for key, value in headers.items():
            if key.lower() in ('authorization', 'cookie', 'x-api-key'):
                safe_headers[key] = '[MASKED]'
            else:
                safe_headers[key] = value

    extra = {
        'http_method': method,
        'url': url,
        'headers': safe_headers,
        'request_type': 'outgoing',
    }

    logger.info(f"{method} {url}", extra=extra)


def log_response(
    status_code: int,
    url: str,
    response_time_ms: int,
    content_length: Optional[int] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Log HTTP response.

    Args:
        status_code: HTTP status code
        url: Request URL
        response_time_ms: Response time in milliseconds
        content_length: Response content length in bytes
        logger: Logger to use
    """
    if logger is None:
        logger = get_logger('http.response')

    extra = {
        'status_code': status_code,
        'url': url,
        'response_time': response_time_ms,
        'response_type': 'received',
    }

    if content_length is not None:
        extra['content_length'] = content_length

    level = logging.INFO if 200 <= status_code < 400 else logging.WARNING
    logger.log(level, f"Response {status_code} from {url} in {response_time_ms}ms", extra=extra)


# Context managers for structured logging

class LoggingContext:
    """Context manager for setting logging context."""

    def __init__(
        self,
        correlation_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        task_id: Optional[str] = None,
    ):
        """
        Initialize logging context.

        Args:
            correlation_id: Correlation ID for this context
            agent_name: Agent name for this context
            task_id: Task ID for this context
        """
        self.correlation_id = correlation_id
        self.agent_name = agent_name
        self.task_id = task_id
        self.previous_correlation_id: Optional[str] = None

    def __enter__(self) -> str:
        """Enter logging context."""
        self.previous_correlation_id = get_correlation_id()
        actual_correlation_id = set_correlation_id(self.correlation_id)

        # Log context entry
        logger = get_logger('context')
        extra = {}
        if self.agent_name:
            extra['agent_name'] = self.agent_name
        if self.task_id:
            extra['task_id'] = self.task_id

        logger.debug("Entering logging context", extra=extra)

        return actual_correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit logging context."""
        logger = get_logger('context')

        if exc_type is not None:
            logger.debug(f"Exiting logging context with error: {exc_type.__name__}")
        else:
            logger.debug("Exiting logging context")

        # Restore previous correlation ID
        if self.previous_correlation_id:
            correlation_id_var.set(self.previous_correlation_id)
        else:
            clear_correlation_id()


# Initialize logging on module import
setup_logging()