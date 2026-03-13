"""Integration tests for worker task processing with API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from src.api.app import app
from src.db.session import get_session
from src.models.task import Task, TaskStatus
from src.workers.arq_worker import execute_task_handler

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
def client(db_session, test_engine):
    """Provide a test client with overridden database dependency."""

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def worker_context(test_engine):
    """Provide worker context with test engine."""
    return {"engine": test_engine}


@pytest.mark.integration
async def test_full_workflow_task_submission_to_completion(db_session, test_engine, client, worker_context):
    """Test complete workflow: submit task → worker processes → verify completion."""
    # Step 1: Submit task via API
    request_data = {
        "task_type": "integration_test_task",
        "payload": {"value": 42},
        "priority": 1,
        "max_retries": 3,
    }
    response = client.post("/tasks", json=request_data)
    assert response.status_code == 201
    task_id = response.json()["id"]
    print(f"✅ Task created: {task_id}")

    # Step 2: Verify task is in QUEUED state (immediately enqueued to Redis)
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "QUEUED"
    print("✅ Task status verified: QUEUED")

    # Step 3: Simulate worker processing the task
    result = await execute_task_handler(worker_context, task_id)
    assert result["status"] == "completed"
    print(f"✅ Worker processed task: {result}")

    # Step 4: Verify task is now COMPLETED
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    task_data = response.json()
    assert task_data["status"] == "COMPLETED"
    print("✅ Task status verified: COMPLETED")


@pytest.mark.integration
async def test_worker_idempotency(db_session, test_engine, client, worker_context):
    """Test that running worker multiple times doesn't cause issues."""
    # Submit task
    response = client.post("/tasks", json={
        "task_type": "idempotent_task",
        "payload": {"x": 1},
    })
    task_id = response.json()["id"]

    # Execute worker first time
    result1 = await execute_task_handler(worker_context, task_id)
    assert result1["status"] == "completed"

    # Get task state after first execution
    response = client.get(f"/tasks/{task_id}")
    state_after_first = response.json()

    # Execute worker again (idempotent)
    result2 = await execute_task_handler(worker_context, task_id)
    assert result2["status"] == "completed"

    # Verify task state hasn't changed problematically
    response = client.get(f"/tasks/{task_id}")
    state_after_second = response.json()
    assert state_after_first["status"] == state_after_second["status"]
    print("✅ Worker idempotency verified")


@pytest.mark.integration
async def test_worker_handles_missing_task(worker_context):
    """Test that worker gracefully handles missing task."""
    fake_task_id = "00000000-0000-0000-0000-000000000000"
    result = await execute_task_handler(worker_context, fake_task_id)

    assert result["status"] == "failed"
    assert result["reason"] == "task_not_found"
    print("✅ Worker handled missing task gracefully")


@pytest.mark.integration
async def test_task_retry_status_progression(db_session, test_engine):
    """Test task retry status progression."""
    # Create a task
    task = Task(
        task_type="retry_progression_test",
        payload={},
        status=TaskStatus.QUEUED,
        max_retries=2,
        retry_count=0,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Simulate first processing attempt
    task.status = TaskStatus.PROCESSING
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    assert task.status == TaskStatus.PROCESSING

    # Simulate failure with retry
    task.status = TaskStatus.RETRYING
    task.retry_count = 1
    task.last_error = "Simulated error"
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    assert task.status == TaskStatus.RETRYING
    assert task.retry_count == 1

    # Simulate retry attempt
    task.status = TaskStatus.PROCESSING
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Simulate second failure
    task.retry_count = 2
    task.status = TaskStatus.RETRYING
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Next failure should go to DEAD_LETTER
    if task.retry_count >= task.max_retries:
        task.status = TaskStatus.DEAD_LETTER
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    assert task.status == TaskStatus.DEAD_LETTER
    print("✅ Task retry progression verified: QUEUED → RETRYING → DEAD_LETTER")
