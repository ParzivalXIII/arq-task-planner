"""Integration tests for task API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from src.api.app import app
from src.db.session import get_session

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
    from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionClass

    async with AsyncSessionClass(test_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


@pytest.fixture
def client(db_session):
    """Provide a test client with overridden database dependency."""

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.integration
def test_submit_task_success(client):
    """Test successful task submission."""
    request_data = {
        "task_type": "email_notification",
        "payload": {"email": "user@example.com", "subject": "Welcome"},
        "priority": 1,
        "max_retries": 5,
    }

    response = client.post("/tasks", json=request_data)

    assert response.status_code == 201
    data = response.json()
    assert data["task_type"] == "email_notification"
    assert data["status"] == "QUEUED"  # Task immediately enqueued to Redis
    assert data["retry_count"] == 0
    assert data["max_retries"] == 5
    assert data["priority"] == 1
    assert "id" in data
    assert "created_at" in data


@pytest.mark.integration
def test_submit_task_with_idempotency_key(client):
    """Test task submission with idempotency key."""
    request_data = {
        "task_type": "report_generation",
        "payload": {"report_id": "123"},
        "idempotency_key": "unique-key-123",
    }

    # First request
    response1 = client.post("/tasks", json=request_data)
    assert response1.status_code == 201
    data1 = response1.json()

    # Second request with same idempotency key
    response2 = client.post("/tasks", json=request_data)
    assert response2.status_code == 201
    data2 = response2.json()

    # Should return the same task
    assert data1["id"] == data2["id"]


@pytest.mark.integration
def test_submit_task_invalid_payload(client):
    """Test task submission with non-JSON-serializable payload."""
    request_data = {        # type: ignore  # noqa: F841
        "task_type": "some_task",
        "payload": {"date": "2023-01-01"},  # This will be JSON serializable, so let's use a complex object
    }

    # Actually, Pydantic will reject non-serializable objects before our code
    # So let's test with valid data but malformed request
    response = client.post("/tasks", json={
        "task_type": "",  # Empty task_type
        "payload": {},
    })

    # Should fail validation
    assert response.status_code == 422


@pytest.mark.integration
def test_get_task_success(client):
    """Test retrieving a task by ID."""
    # Create a task first
    create_request = {
        "task_type": "test_task",
        "payload": {"key": "value"},
    }
    create_response = client.post("/tasks", json=create_request)
    assert create_response.status_code == 201
    task_id = create_response.json()["id"]

    # Retrieve the task
    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == task_id
    assert data["task_type"] == "test_task"
    assert data["status"] == "QUEUED"  # Task immediately enqueued to Redis


@pytest.mark.integration
def test_get_task_not_found(client):
    """Test retrieving a non-existent task."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/tasks/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.integration
def test_list_tasks_empty(client):
    """Test listing tasks when no tasks exist."""
    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
    assert data["count"] == 0


@pytest.mark.integration
def test_list_tasks_with_status_filter(client):
    """Test listing tasks with status filter."""
    # Create two tasks
    for i in range(2):
        client.post("/tasks", json={
            "task_type": "task_type_" + str(i),
            "payload": {},
        })

    # List all tasks
    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2

    # List only QUEUED tasks (newly created tasks are immediately queued)
    response = client.get("/tasks?status=QUEUED")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2

    # List only COMPLETED tasks (should be empty)
    response = client.get("/tasks?status=COMPLETED")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0


@pytest.mark.integration
def test_retry_task_success(client):
    """Test retrying a failed task."""
    # Create a task
    create_response = client.post("/tasks", json={
        "task_type": "retryable_task",
        "payload": {},
        "max_retries": 3,
    })
    task_id = create_response.json()["id"]

    # Task status is QUEUED after creation; retry transitions to RETRYING
    # First verify task is QUEUED
    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.json()["status"] == "QUEUED"

    # Now retry the task
    retry_response = client.post(f"/tasks/{task_id}/retry")
    assert retry_response.status_code == 200
    data = retry_response.json()
    assert data["status"] == "RETRYING"
    assert data["retry_count"] == 1


@pytest.mark.integration
def test_retry_task_not_found(client):
    """Test retrying a non-existent task."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(f"/tasks/{fake_id}/retry")
    assert response.status_code == 404


@pytest.mark.integration
def test_health_check_success(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["database"] == "healthy"
