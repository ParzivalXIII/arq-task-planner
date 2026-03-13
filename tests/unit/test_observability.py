"""Unit tests for observability and logging utilities."""
import json
import logging

import pytest

from src.observability.logging import JSONFormatter, PerformanceTimer, setup_logging


def test_json_formatter_basic():
    """Test basic JSON formatting."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    result = formatter.format(record)
    data = json.loads(result)

    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert data["message"] == "Test message"
    assert "timestamp" in data


def test_json_formatter_with_extra_fields():
    """Test JSON formatting with extra fields."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="worker",
        level=logging.INFO,
        pathname="worker.py",
        lineno=100,
        msg="Task executed",
        args=(),
        exc_info=None,
    )

    # Add extra fields
    record.task_id = "task-123"
    record.task_type = "email"
    record.duration_ms = 1234.5

    result = formatter.format(record)
    data = json.loads(result)

    assert data["task_id"] == "task-123"
    assert data["task_type"] == "email"
    assert data["duration_ms"] == 1234.5


def test_setup_logging_returns_logger():
    """Test that setup_logging returns a configured logger."""
    logger = setup_logging("test_logger_setup", level=logging.DEBUG)

    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger_setup"
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) > 0


def test_setup_logging_creates_json_handler():
    """Test that setup_logging creates a JSON handler."""
    logger = setup_logging("test_json_handler", level=logging.INFO)

    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler.formatter, JSONFormatter)


@pytest.mark.asyncio
async def test_performance_timer_context_manager_success():
    """Test PerformanceTimer measures execution time."""
    logger = setup_logging("timer_test", level=logging.INFO)

    with PerformanceTimer(logger, "task-456") as timer:
        import asyncio
        await asyncio.sleep(0.01)

    assert timer.start_time is not None
    assert timer.end_time is not None
    assert timer.end_time > timer.start_time
    duration = (timer.end_time - timer.start_time) * 1000
    assert duration >= 10  # At least 10ms


@pytest.mark.asyncio
async def test_performance_timer_context_manager_error():
    """Test PerformanceTimer handles errors."""
    logger = setup_logging("timer_error_test", level=logging.INFO)

    with pytest.raises(ValueError):
        with PerformanceTimer(logger, "task-789"):
            raise ValueError("Test error")
