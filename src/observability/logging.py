"""Structured logging and observability utilities."""
import json
import logging
import time
from datetime import datetime

from src.core.config import settings


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": settings.env,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id        # type: ignore
        if hasattr(record, "task_type"):
            log_data["task_type"] = record.task_type    # type: ignore
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms    # type: ignore
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id    # type: ignore

        return json.dumps(log_data)


def setup_logging(
    name: str,
    level: int | None = None,
) -> logging.Logger:
    """
    Set up structured logging with JSON formatter.

    Args:
        name: Logger name (usually module name or component name)
        level: Logging level. If None, uses settings.log_level_int

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Use provided level or fall back to configured level
    log_level = level or settings.log_level_int
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers = []

    # Create console handler with JSON formatter
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.setLevel(log_level)
    logger.addHandler(handler)

    # Suppress propagation to avoid duplicate logs
    logger.propagate = False

    return logger


# Module-level logger instance
logger = setup_logging(__name__)


class PerformanceTimer:
    """Context manager for measuring task execution time."""

    def __init__(self, logger: logging.Logger, task_id: str):
        """Initialize timer."""
        self.logger = logger
        self.task_id = task_id
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        """Start timer."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timer and log duration."""
        self.end_time = time.time()
        assert self.start_time is not None and self.end_time is not None and (self.end_time - self.start_time) * 1000
        duration_ms = (self.end_time - self.start_time) * 1000

        extra = {"task_id": self.task_id, "duration_ms": duration_ms}

        if exc_type:
            self.logger.error(
                f"Task execution failed after {duration_ms:.2f}ms",
                extra=extra,
            )
        else:
            self.logger.info(
                f"Task execution completed in {duration_ms:.2f}ms",
                extra=extra,
            )

        return False
