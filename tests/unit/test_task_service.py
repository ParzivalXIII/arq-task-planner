
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from src.models.task import TaskStatus
from src.services.task_service import TaskService


@pytest.fixture
async def session():
    """Create an async SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = AsyncSession(engine, expire_on_commit=False)
    yield async_session
    await async_session.close()
    await engine.dispose()


@pytest.fixture
async def service(session):
    return TaskService(session=session)


@pytest.mark.asyncio
async def test_create_task_and_retrieve(service):
    t = await service.create_task("email.send", {"to": "a@b.com"})
    assert t.id is not None
    assert t.task_type == "email.send"
    assert t.status == TaskStatus.QUEUED  # Immediately enqueued to Redis

    fetched = await service.get_task(t.id)
    assert fetched is not None
    assert fetched.id == t.id


@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicates(service):
    key = "123"
    t1 = await service.create_task("x", {}, idempotency_key=key)
    t2 = await service.create_task("x", {}, idempotency_key=key)
    assert t1.id == t2.id


@pytest.mark.asyncio
async def test_invalid_payload_rejected(service):
    with pytest.raises(ValueError):
        await service.create_task("x", {"bad": object()})


@pytest.mark.asyncio
async def test_list_tasks_filter(service):
    await service.create_task("a", {})
    await service.create_task("b", {}, priority=1)
    results = await service.list_tasks()
    assert len(results) == 2


@pytest.mark.asyncio
async def test_update_status_valid_transition(service):
    t = await service.create_task("a", {})
    # Task starts as QUEUED, transition to PROCESSING
    updated = await service.update_status(t, TaskStatus.PROCESSING)
    assert updated.status == TaskStatus.PROCESSING


@pytest.mark.asyncio
async def test_update_status_invalid_transition(service):
    t = await service.create_task("a", {})
    with pytest.raises(ValueError):
        await service.update_status(t, TaskStatus.COMPLETED)


@pytest.mark.asyncio
async def test_retry_task_behavior(service):
    t = await service.create_task("a", {})
    # Task starts as QUEUED; retry transitions to RETRYING
    r = await service.retry_task(t.id)
    assert r.retry_count == 1
    assert r.status == TaskStatus.RETRYING

    # simulate reaching max
    r.max_retries = 1
    service.session.add(r)
    await service.session.commit()
    r2 = await service.retry_task(r.id)
    assert r2.status == TaskStatus.DEAD_LETTER
