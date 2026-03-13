"""Additional API endpoint tests for error scenarios and edge cases."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from src.api.app import app
from src.db.session import get_session

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
def test_submit_task_with_default_values(client):
    """Test task submission with minimal required fields."""
    request_data = {
        "task_type": "minimal_task",
        "payload": {},
    }

    response = client.post("/tasks", json=request_data)
    assert response.status_code == 201
    data = response.json()
    assert data["priority"] == 0
    assert data["max_retries"] == 3


@pytest.mark.integration
def test_submit_task_boundary_values(client):
    """Test task submission with boundary priority values."""
    # Min priority
    response = client.post("/tasks", json={
        "task_type": "boundary_task",
        "payload": {},
        "priority": 0,
    })
    assert response.status_code == 201

    # Max priority
    response = client.post("/tasks", json={
        "task_type": "boundary_task",
        "payload": {},
        "priority": 100,
    })
    assert response.status_code == 201


@pytest.mark.integration
def test_submit_task_invalid_priority_negative(client):
    """Test task submission with negative priority."""
    response = client.post("/tasks", json={
        "task_type": "task",
        "payload": {},
        "priority": -1,
    })
    assert response.status_code == 422


@pytest.mark.integration
def test_submit_task_invalid_priority_too_high(client):
    """Test task submission with priority > 100."""
    response = client.post("/tasks", json={
        "task_type": "task",
        "payload": {},
        "priority": 101,
    })
    assert response.status_code == 422


@pytest.mark.integration
def test_list_tasks_multiple_pages_concept(client):
    """Test listing tasks with multiple results."""
    # Create 5 tasks
    task_ids = []
    for i in range(5):
        response = client.post("/tasks", json={
            "task_type": f"task_{i}",
            "payload": {"index": i},
        })
        assert response.status_code == 201
        task_ids.append(response.json()["id"])

    # List all
    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5
    assert len(data["tasks"]) == 5

    # Verify all task IDs are present
    returned_ids = [t["id"] for t in data["tasks"]]
    for task_id in task_ids:
        assert task_id in returned_ids


@pytest.mark.integration
def test_list_tasks_various_statuses(client):
    """Test listing tasks with different status filters."""
    # Create a task
    response = client.post("/tasks", json={
        "task_type": "multi_status",
        "payload": {},
    })
    task_id = response.json()["id"]  # type: ignore  # noqa: F841

    # Test filtering by each valid status
    valid_statuses = [
        "PENDING", "QUEUED", "PROCESSING",
        "COMPLETED", "FAILED", "RETRYING", "DEAD_LETTER"
    ]

    for status in valid_statuses:
        response = client.get(f"/tasks?status={status}")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "count" in data
        # Only QUEUED should have the task (since we didn't modify it)
        if status == "QUEUED":
            assert data["count"] == 1
        else:
            assert data["count"] == 0


@pytest.mark.integration
def test_invalid_uuid_in_get_task(client):
    """Test getting task with invalid UUID format."""
    response = client.get("/tasks/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.integration
def test_invalid_uuid_in_retry(client):
    """Test retrying task with invalid UUID format."""
    response = client.post("/tasks/invalid-uuid/retry")
    assert response.status_code == 422


@pytest.mark.integration
def test_task_with_large_payload(client):
    """Test task submission with large payload."""
    large_payload = {
        "data": "x" * 10000,  # Large string
        "nested": {
            "deep": {
                "structure": [1, 2, 3, 4, 5] * 100
            }
        }
    }

    response = client.post("/tasks", json={
        "task_type": "large_payload_task",
        "payload": large_payload,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["payload"]["data"] == "x" * 10000


@pytest.mark.integration
def test_task_with_complex_json_payload(client):
    """Test task with complex nested JSON payload."""
    payload = {
        "user_id": 123,
        "actions": ["click", "scroll", "submit"],
        "metadata": {
            "browser": "Chrome",
            "os": "Linux",
            "version": "1.0.0"
        }
    }

    response = client.post("/tasks", json={
        "task_type": "user_action",
        "payload": payload,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["payload"]["user_id"] == 123
    assert "browser" in data["payload"]["metadata"]


@pytest.mark.integration
def test_task_with_unicode_characters(client):
    """Test task with unicode characters in payload."""
    payload = {
        "message": "Hello 世界 مرحبا мир",
        "emoji": "🚀🎉💻"
    }

    response = client.post("/tasks", json={
        "task_type": "unicode_task",
        "payload": payload,
    })
    assert response.status_code == 201
    data = response.json()
    assert "世界" in data["payload"]["message"]
    assert data["payload"]["emoji"] == "🚀🎉💻"


@pytest.mark.integration
def test_retry_multiple_times(client):
    """Test retrying a task multiple times."""
    # Create task with max_retries=3
    response = client.post("/tasks", json={
        "task_type": "multi_retry",
        "payload": {},
        "max_retries": 3,
    })
    task_id = response.json()["id"]

    # Retry 3 times
    for i in range(3):
        response = client.post(f"/tasks/{task_id}/retry")
        assert response.status_code == 200
        data = response.json()
        # First retry transitions from QUEUED to RETRYING, subsequent retries stay RETRYING
        assert data["retry_count"] == i + 1
        assert data["status"] == "RETRYING"

    # Fourth retry should fail (max retries exceeded)
    response = client.post(f"/tasks/{task_id}/retry")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DEAD_LETTER"  # Should be dead-lettered


@pytest.mark.integration
def test_health_endpoint_structure(client):
    """Test health endpoint returns correct structure."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert "healthy" in data["database"] or "unhealthy" in data["database"]
