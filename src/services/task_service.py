from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.config import settings
from src.db.session import get_session
from src.models.task import Task, TaskStatus
from src.observability.metrics import get_metrics_collector

# state machine definition from PRD
_ALLOWED_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.QUEUED},
    TaskStatus.QUEUED: {TaskStatus.PROCESSING},
    TaskStatus.PROCESSING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.RETRYING},
    TaskStatus.RETRYING: {TaskStatus.QUEUED, TaskStatus.DEAD_LETTER},
}


def _validate_transition(current: TaskStatus, new: TaskStatus) -> None:
    """Raise if the transition is not allowed."""
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ValueError(f"invalid transition {current} -> {new}")


def _serialize_payload(payload: dict) -> str:
    try:
        return json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must be JSON serializable") from exc


def _validate_payload(payload: dict) -> bool:
    try:
        _serialize_payload(payload)
        return True
    except ValueError:
        return False


class TaskService:
    def __init__(self, session: AsyncSession, redis_url: str | None = None):
        self.session = session
        self.redis_url = redis_url or settings.redis_url
        self.redis_pool = None

    async def _get_redis_pool(self):
        """Lazily initialize Redis pool for ARQ."""
        if self.redis_pool is None:
            redis_settings = RedisSettings.from_dsn(self.redis_url)
            self.redis_pool = await create_pool(redis_settings)
        return self.redis_pool

    async def publish_event(self, task: Task) -> None:
        """Enqueue task via ARQ for worker processing."""
        try:
            pool = await self._get_redis_pool()
            # Enqueue the execute_task_handler job with the task ID
            await pool.enqueue_job("execute_task_handler", str(task.id))

            # Update task status to QUEUED only if it's currently PENDING
            # (preserve RETRYING status for retry operations)
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.QUEUED
                task.updated_at = datetime.now(UTC)
                self.session.add(task)
                await self.session.commit()
        except Exception as e:
            # Log but don't fail - task is still in database
            print(f"Failed to enqueue task {task.id}: {e}")

    async def create_task(
        self,
        task_type: str,
        payload: dict,
        priority: int = 0,
        max_retries: int = 3,
        idempotency_key: str | None = None,
    ) -> Task:
        """Create a new task and optionally publish an event.

        If an idempotency_key is provided and a matching task already exists,
        the existing task is returned instead of creating a duplicate.
        """
        if not _validate_payload(payload):
            raise ValueError("payload must be JSON serializable")

        if idempotency_key:
            result = await self.session.execute(
                select(Task).where(Task.idempotency_key == idempotency_key)
            )
            existing = result.scalars().first()
            if existing:
                return existing

        task = Task(
            task_type=task_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
            idempotency_key=idempotency_key,
        )
        self.session.add(task)
        try:
            await self.session.commit()
            await self.session.refresh(task)
        except SQLAlchemyError:
            await self.session.rollback()
            raise

        # publish event after commit
        await self.publish_event(task)
        
        # Record task submission for observability
        get_metrics_collector().record_task_submission()
        
        return task

    async def get_task(self, task_id: UUID) -> Task | None:
        return await self.session.get(Task, task_id)

    async def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        stmt = select(Task)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, task: Task, new_status: TaskStatus) -> Task:
        _validate_transition(task.status, new_status)
        task.status = new_status
        # update timestamp manually with timezone-aware UTC
        task.updated_at = datetime.now(UTC)
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def retry_task(self, task_id: UUID) -> Task:
        task = await self.get_task(task_id)
        if not task:
            raise ValueError("task not found")
        if task.retry_count >= task.max_retries:
            task.status = TaskStatus.DEAD_LETTER
            self.session.add(task)
            await self.session.commit()
            await self.session.refresh(task)
            
            # Record dead letter for observability
            get_metrics_collector().record_dead_letter()
            
            return task

        task.retry_count += 1
        task.status = TaskStatus.RETRYING
        task.updated_at = datetime.now(UTC)
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)

        # Record task retry for observability
        get_metrics_collector().record_task_retry()
        
        await self.publish_event(task)
        return task


# convenience dependency for FastAPI
from collections.abc import AsyncGenerator  # noqa: E402


async def get_task_service(
    session: AsyncSession = Depends(get_session),  # noqa: B008
    redis_url: str | None = None
) -> AsyncGenerator[TaskService, None]:
    service = TaskService(session=session, redis_url=redis_url)
    yield service
