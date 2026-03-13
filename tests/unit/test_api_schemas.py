"""Unit tests for API schemas and validation."""

import pytest

from src.api.schemas.task import (
    HealthCheckResponse,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
)
from src.models.task import TaskStatus


def test_task_create_request_validation_success():
    """Test valid TaskCreateRequest."""
    req = TaskCreateRequest(
        task_type="test_task",
        payload={"key": "value"},
        priority=5,
        max_retries=3,
        idempotency_key="key123",
    )
    assert req.task_type == "test_task"
    assert req.priority == 5
    assert req.max_retries == 3


@pytest.mark.parametrize("priority,valid", [
    (0, True),
    (50, True),
    (100, True),
    (-1, False),
    (101, False),
])
def test_task_create_request_priority_validation(priority, valid):
    """Test priority field validation."""
    if valid:
        req = TaskCreateRequest(
            task_type="task",
            payload={},
            priority=priority,
        )       # type: ignore  # noqa: F841
        assert req.priority == priority
    else:
        with pytest.raises(ValueError):
            TaskCreateRequest(
                task_type="task",
                payload={},
                priority=priority,
            )       # type: ignore  # noqa: F841


@pytest.mark.parametrize("max_retries,valid", [
    (0, True),
    (5, True),
    (10, True),
    (-1, False),
    (11, False),
])
def test_task_create_request_max_retries_validation(max_retries, valid):
    """Test max_retries field validation."""
    if valid:
        req = TaskCreateRequest(
            task_type="task",
            payload={},
            max_retries=max_retries,
        )       # type: ignore  # noqa: F841
        assert req.max_retries == max_retries
    else:
        with pytest.raises(ValueError):
            TaskCreateRequest(
                task_type="task",
                payload={},
                max_retries=max_retries,
            )       # type: ignore  # noqa: F841


def test_task_create_request_empty_task_type():
    """Test that empty task_type is rejected."""
    with pytest.raises(ValueError):
        TaskCreateRequest(
            task_type="",
            payload={},
        )       # type: ignore  # noqa: F841


def test_task_response_from_model():
    """Test TaskResponse can be created from model."""
    from datetime import datetime
    from uuid import uuid4

    from src.models.task import Task

    task = Task(
        id=uuid4(),
        task_type="test",
        payload={"key": "value"},
        status=TaskStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    response = TaskResponse.model_validate(task)
    assert response.id == task.id
    assert response.task_type == "test"
    assert response.status == TaskStatus.PENDING


def test_task_list_response_serialization():
    """Test TaskListResponse serialization."""
    resp = TaskListResponse(tasks=[], count=0)
    json_data = resp.model_dump_json()
    assert "tasks" in json_data
    assert "count" in json_data


def test_health_check_response_healthy():
    """Test HealthCheckResponse for healthy status."""
    resp = HealthCheckResponse(
        status="healthy",
        database="healthy",
        redis="healthy",
    )
    assert resp.status == "healthy"
    assert resp.database == "healthy"
    assert resp.redis == "healthy"


def test_health_check_response_degraded():
    """Test HealthCheckResponse for degraded status."""
    resp = HealthCheckResponse(
        status="degraded",
        database="healthy",
        redis="unhealthy: connection failed",
    )
    assert resp.status == "degraded"
    assert "unhealthy" in resp.redis            # type: ignore  # noqa: F821
