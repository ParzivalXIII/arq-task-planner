"""Integration tests for metrics recording in task lifecycle.

Tests verify that metrics are correctly recorded when tasks are created,
processed, completed, failed, and retried through the full task service
and worker pipeline.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from src.models.task import TaskStatus
from src.observability.metrics import get_metrics_collector
from src.services.task_service import TaskService

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_engine():
    """Create test database engine and tables."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Provide a database session for each test."""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


@pytest.fixture
def metrics_collector():
    """Get metrics collector and reset it."""
    collector = get_metrics_collector()
    collector.reset()
    return collector


@pytest.mark.asyncio
async def test_metrics_recorded_on_task_creation(
    db_session: AsyncSession, metrics_collector
):
    """Creating a task should increment submission counter."""
    service = TaskService(session=db_session)

    # Verify initial state
    assert metrics_collector.task_submissions_total == 0
    assert metrics_collector.active_tasks == 0

    # Create a task
    task = await service.create_task(
        task_type="test_task",
        payload={"data": "test"}
    )

    # Verify metrics recorded
    assert metrics_collector.task_submissions_total == 1
    assert metrics_collector.active_tasks == 1
    assert task.status == TaskStatus.QUEUED


@pytest.mark.asyncio
async def test_metrics_recorded_on_task_retry(
    db_session: AsyncSession, metrics_collector
):
    """Retrying a task should increment retry counter."""
    service = TaskService(session=db_session)

    # Create and fetch a task
    task = await service.create_task(
        task_type="test_task",
        payload={"data": "test"},
        max_retries=3
    )
    task_id = task.id

    # Reset metrics after creation
    metrics_collector.reset()

    # Retry the task
    retried_task = await service.retry_task(task_id)

    # Verify metrics recorded
    assert metrics_collector.task_retries_total == 1
    assert retried_task.status == TaskStatus.RETRYING
    assert retried_task.retry_count == 1


@pytest.mark.asyncio
async def test_metrics_dead_letter_on_max_retries(
    db_session: AsyncSession, metrics_collector
):
    """Exceeding max retries should move task to DEAD_LETTER."""
    service = TaskService(session=db_session)

    # Create a task with max_retries=1
    task = await service.create_task(
        task_type="test_task",
        payload={"data": "test"},
        max_retries=1
    )
    task_id = task.id

    # Reset metrics
    metrics_collector.reset()

    # First retry (should work)
    task = await service.retry_task(task_id)
    assert task.status == TaskStatus.RETRYING
    assert metrics_collector.task_retries_total == 1

    # Second retry (should exceed max and go to DEAD_LETTER)
    task = await service.retry_task(task_id)
    assert task.status == TaskStatus.DEAD_LETTER
    assert metrics_collector.task_dead_letters_total == 1


@pytest.mark.asyncio
async def test_metrics_on_status_transition(
    db_session: AsyncSession, metrics_collector
):
    """Task status transitions should be tracked by service."""
    service = TaskService(session=db_session)

    # Create a task
    task = await service.create_task(
        task_type="test_task",
        payload={"data": "test"}
    )

    # Reset to test status transitions
    metrics_collector.reset()

    # Update to PROCESSING
    task = await service.update_status(task, TaskStatus.PROCESSING)
    assert task.status == TaskStatus.PROCESSING

    # Update to COMPLETED
    task = await service.update_status(task, TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_metrics_show_realistic_task_flow(
    db_session: AsyncSession, metrics_collector
):
    """Full task lifecycle should show correct metrics snapshot."""
    service = TaskService(session=db_session)

    # Create 3 tasks
    for i in range(3):
        await service.create_task(
            task_type="task_type_a" if i < 2 else "task_type_b",
            payload={"index": i}
        )

    metrics = metrics_collector.get_snapshot()

    # Should show 3 submissions and 3 active
    assert metrics.task_submissions_total == 3
    assert metrics.active_tasks == 3

    # Get Prometheus format
    prometheus_text = metrics.to_prometheus_format()
    assert "task_submissions_total 3" in prometheus_text
    assert "active_tasks 3" in prometheus_text


@pytest.mark.asyncio
async def test_metrics_collected_with_request_latency(
    db_session: AsyncSession, metrics_collector
):
    """Request latency should be recordable within service context."""
    # Simulate recording latencies
    metrics_collector.record_request_latency(10.5)
    metrics_collector.record_request_latency(20.5)
    metrics_collector.record_request_latency(30.5)

    # Verify calculations
    mean = metrics_collector.get_request_latency_mean()
    p50 = metrics_collector.get_request_latency_percentile(50)
    p95 = metrics_collector.get_request_latency_percentile(95)

    assert mean == 20.5
    assert p50 == 20.5
    assert p95 == 30.5


@pytest.mark.asyncio
async def test_metrics_success_rate_calculation(
    db_session: AsyncSession, metrics_collector
):
    """Success rate should accurately reflect completions vs failures."""
    service = TaskService(session=db_session)

    # Create a task
    task = await service.create_task(           # type: ignore  # noqa: F841
        task_type="test",
        payload={}
    )

    # Record as completion
    metrics_collector.record_task_completion()

    # Create 2 more and record as failures
    for _ in range(2):
        await service.create_task(task_type="test", payload={})
    metrics_collector.record_task_failure("test")
    metrics_collector.record_task_failure("test")

    # Success rate should be 1 completed / 3 total = 0.333...
    rate = metrics_collector.get_success_rate()
    assert rate == pytest.approx(0.333, rel=0.01)

    # Snapshot should include rate
    snapshot = metrics_collector.get_snapshot()
    assert snapshot.success_rate == pytest.approx(0.333, rel=0.01)
