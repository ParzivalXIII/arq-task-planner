"""Task submission, retrieval, and retry routes."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from src.api.schemas.task import TaskCreateRequest, TaskListResponse, TaskResponse
from src.models.task import TaskStatus
from src.services.task_service import TaskService, get_task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new task",
    description="Create a new task and queue it for processing.",
)
async def submit_task(
    request: TaskCreateRequest,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """
    Submit a new task for processing.

    **Parameters:**
    - `task_type`: The type/category of the task
    - `payload`: JSON-serializable task data
    - `priority`: Priority level (0-100, higher = more urgent)
    - `max_retries`: Maximum number of retry attempts (0-10)
    - `idempotency_key`: Optional key for idempotent requests

    **Returns:**
    - Created task with ID and initial status (PENDING)

    **Status Codes:**
    - 201: Task created successfully
    - 400: Invalid request (non-JSON-serializable payload, etc.)
    - 409: Duplicate task (same idempotency_key already exists)
    """
    try:
        task = await task_service.create_task(
            task_type=request.task_type,
            payload=request.payload,
            priority=request.priority,
            max_retries=request.max_retries,
            idempotency_key=request.idempotency_key,
        )
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except IntegrityError as e:
        # Idempotency key conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task with idempotency_key already exists: {request.idempotency_key}",
        ) from e


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Retrieve task details",
    description="Get details of a specific task by ID.",
)
async def get_task(
    task_id: UUID,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """
    Get a specific task by ID.

    **Parameters:**
    - `task_id`: UUID of the task

    **Returns:**
    - Task details including status, payload, and retry information

    **Status Codes:**
    - 200: Task found and returned
    - 404: Task not found
    """
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List tasks with optional filtering",
    description="Retrieve a list of tasks, optionally filtered by status.",
)
async def list_tasks(
    task_service: Annotated[TaskService, Depends(get_task_service)],
    status: Annotated[TaskStatus | None, Query(description="Filter by task status")] = None,
) -> TaskListResponse:
    """
    List all tasks with optional status filtering.

    **Parameters:**
    - `status`: Optional status filter (PENDING, QUEUED, PROCESSING, COMPLETED, FAILED, RETRYING, DEAD_LETTER)

    **Returns:**
    - List of tasks matching the filter criteria

    **Status Codes:**
    - 200: List retrieved successfully
    """
    tasks = await task_service.list_tasks(status=status)
    return TaskListResponse(tasks=[TaskResponse.model_validate(t) for t in tasks], count=len(tasks))


@router.post(
    "/{task_id}/retry",
    response_model=TaskResponse,
    summary="Retry a failed task",
    description="Manually retry a task that has failed or been dead-lettered.",
)
async def retry_task(
    task_id: UUID,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """
    Retry a task manually.

    **Parameters:**
    - `task_id`: UUID of the task to retry

    **Returns:**
    - Updated task with incremented retry_count and status

    **Status Codes:**
    - 200: Task retry initiated successfully
    - 404: Task not found
    - 400: Task cannot be retried (invalid state or max retries exceeded)
    """
    try:
        task = await task_service.retry_task(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg) from e
