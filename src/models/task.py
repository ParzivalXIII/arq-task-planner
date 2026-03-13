from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, Index
from sqlmodel import JSON, Field, SQLModel


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    DEAD_LETTER = "DEAD_LETTER"


class Task(SQLModel, table=True):

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    task_type: str = Field(index=True)
    # use generic JSON type to stay compatible with SQLite in tests
    payload: dict = Field(sa_column=Column(JSON))
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True)
    retry_count: int = Field(default=0, nullable=False)
    max_retries: int = Field(default=3, nullable=False)
    priority: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_error: str | None = Field(default=None, nullable=True)
    idempotency_key: str | None = Field(default=None, index=True, nullable=True, unique=True)

    # composite index status+created_at
    __table_args__ = (
        Index("ix_tasks_status_created_at", "status", "created_at"),
    )
