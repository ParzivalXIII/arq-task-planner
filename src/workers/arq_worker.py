"""ARQ worker configuration and initialization."""
import logging
from datetime import UTC, datetime
from uuid import UUID

from arq import Retry
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.core.config import settings
from src.db.session import engine as default_engine
from src.models.task import Task, TaskStatus
from src.observability.logging import logger as structured_logger

# Configure logging
logger = logging.getLogger(__name__)


async def startup(ctx):
    """Initialize worker context (called once on worker startup)."""
    structured_logger.info("🚀 Worker starting up")
    # Create async engine for this worker process with settings
    ctx["engine"] = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=settings.db_pool_size if "sqlite" not in settings.database_url else 0,
        max_overflow=settings.db_max_overflow if "sqlite" not in settings.database_url else 0,
    )
    structured_logger.info("✅ Worker startup complete")


async def shutdown(ctx):
    """Clean up worker context (called once on worker shutdown)."""
    structured_logger.info("🛑 Worker shutting down")
    if "engine" in ctx:
        await ctx["engine"].dispose()
    structured_logger.info("✅ Worker shutdown complete")


async def get_task_from_db(task_id: str, engine) -> Task | None:
    """Helper to fetch a task from database."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine) as session:
        task_uuid = UUID(task_id)
        return await session.get(Task, task_uuid)


async def execute_task_handler(ctx, task_id: str) -> dict:
    """
    Main ARQ task handler: execute a task by ID.

    This is the core worker function that:
    1. Fetches task from database
    2. Updates status to PROCESSING
    3. Executes placeholder handler logic
    4. Updates status to COMPLETED or FAILED
    5. Retries on failure up to max_retries

    **Parameters:**
    - task_id: UUID of the task to process

    **Returns:**
    - dict with execution result

    **Raises:**
    - Retry: if the handler fails and retries are available
    """
    engine = ctx.get("engine", default_engine)
    task_id_str = str(task_id)

    try:
        # Fetch task
        task = await get_task_from_db(task_id_str, engine)
        if not task:
            logger.error(f"Task {task_id_str} not found")
            return {"status": "failed", "reason": "task_not_found"}

        logger.info(f"🔄 Processing task {task_id_str} (type: {task.task_type})")

        # Update status to PROCESSING
        async with AsyncSession(engine) as session:
            task_db = await session.get(Task, task.id)
            if not task_db:
                return {"status": "failed", "reason": "task_disappeared"}

            task_db.status = TaskStatus.PROCESSING
            task_db.updated_at = datetime.now(UTC)
            session.add(task_db)
            await session.commit()

        # Execute task handler logic
        # This is a placeholder—in production, route to specific handlers by task_type
        result = await _execute_task_logic(task)

        # Update status to COMPLETED
        async with AsyncSession(engine) as session:
            task_db = await session.get(Task, task.id)
            task_db.status = TaskStatus.COMPLETED       # type: ignore
            task_db.updated_at = datetime.now(UTC)      # type: ignore
            session.add(task_db)
            await session.commit()

        logger.info(f"✅ Task {task_id_str} completed successfully")
        return {"status": "completed", "result": result}

    except Exception as e:
        logger.exception(f"❌ Task {task_id_str} failed: {str(e)}")

        # Fetch task to check retry count
        async with AsyncSession(engine) as session:
            task_db = await session.get(Task, task.id)      # type: ignore
            if not task_db:
                return {"status": "failed", "reason": "task_disappeared_on_error"}

            # Mark as FAILED or RETRYING based on retry count
            if task_db.retry_count >= task_db.max_retries:
                task_db.status = TaskStatus.DEAD_LETTER
                logger.warning(f"⚠️  Task {task_id_str} moved to DEAD_LETTER (max retries exceeded)")
            else:
                task_db.status = TaskStatus.RETRYING
                task_db.retry_count += 1
                logger.info(f"🔄 Task {task_id_str} marked for retry ({task_db.retry_count}/{task_db.max_retries})")

            task_db.last_error = str(e)
            task_db.updated_at = datetime.now(UTC)
            session.add(task_db)
            await session.commit()

        # If retries available, retry with exponential backoff
        if task_db.retry_count < task_db.max_retries:
            # Exponential backoff: 2^retry_count seconds
            backoff_seconds = 2 ** task_db.retry_count
            raise Retry(defer=backoff_seconds) from e

        return {
            "status": "failed",
            "reason": "max_retries_exceeded",
            "error": str(e),
        }


async def _execute_task_logic(task: Task) -> dict:
    """
    Execute the actual task logic based on task_type.

    This is a placeholder implementation. In a real system, this would:
    - Route to specific handlers by task_type
    - Execute complex business logic
    - Validate outputs
    - etc.

    **Parameters:**
    - task: Task object to execute

    **Returns:**
    - dict with execution result
    """
    # Placeholder: simulated task execution
    logger.debug(f"Executing task logic for {task.task_type}")

    # Example: echo the payload back as result
    result = {
        "task_type": task.task_type,
        "payload_received": task.payload,
        "processed_at": datetime.now(UTC).isoformat(),
    }

    return result


class WorkerConfig:
    """ARQ worker configuration using centralized settings."""

    # Redis connection URL
    redis_url = settings.redis_url

    # Task handlers
    functions = [execute_task_handler]

    # Lifecycle functions
    on_startup = startup
    on_shutdown = shutdown

    # Job settings from centralized configuration
    job_timeout = settings.job_timeout
    keep_result = settings.keep_result
    result_ttl = settings.result_ttl
