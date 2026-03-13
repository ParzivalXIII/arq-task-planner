"""Task-related request and response schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.task import TaskStatus


class TaskCreateRequest(BaseModel):
    """Request schema for creating a new task."""

    task_type: str = Field(..., min_length=1, max_length=255, description="Type of task")
    payload: dict = Field(default_factory=dict, description="Task payload (must be JSON serializable)")
    priority: int = Field(default=0, ge=0, le=100, description="Task priority (0-100)")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    idempotency_key: str | None = Field(
        None, max_length=255, description="Optional idempotency key for deduplication"
    )

    model_config = {"json_schema_extra": {"examples": [
        {
            "task_type": "email_notification",
            "payload": {"email": "user@example.com", "subject": "Welcome"},
            "priority": 1,
            "max_retries": 5,
        }
    ]}}


class TaskResponse(BaseModel):
    """Response schema for a task."""

    id: UUID = Field(description="Unique task identifier")
    task_type: str = Field(description="Type of task")
    payload: dict = Field(description="Task payload")
    status: TaskStatus = Field(description="Current task status")
    retry_count: int = Field(description="Current retry count")
    max_retries: int = Field(description="Maximum retry attempts")
    priority: int = Field(description="Task priority (0-100)")
    created_at: datetime = Field(description="Task creation timestamp")
    updated_at: datetime = Field(description="Task last update timestamp")
    last_error: str | None = Field(None, description="Error message from last failure")

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Response schema for listing tasks."""

    tasks: list[TaskResponse] = Field(description="List of tasks")
    count: int = Field(description="Total number of tasks")

    model_config = {"json_schema_extra": {"examples": [
        {"tasks": [], "count": 0}
    ]}}


class HealthCheckResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str = Field(description="Overall health status: 'healthy' or 'degraded'")
    database: str = Field(description="Database connectivity status")
    redis: str | None = Field(None, description="Redis connectivity status")
