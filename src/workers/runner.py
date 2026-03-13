"""Worker process entry point for ARQ consumer."""
import asyncio
import sys

from arq.connections import RedisSettings, create_pool
from arq.worker import Worker

from src.core.config import settings
from src.observability.logging import logger, setup_logging
from src.workers.arq_worker import WorkerConfig


async def run_worker() -> None:
    """
    Run the ARQ worker with proper configuration.

    Configuration is loaded from centralized settings object.
    Uses structured JSON logging for all output.

    Important: This function runs within asyncio.run() context, so we don't call
    worker.run() which tries to create its own event loop. Instead, we await the
    worker's main task directly.
    """
    logger.info(
        "Starting ARQ worker",
        extra={
            "redis_url": settings.redis_url,
            "log_level": settings.log_level,
            "job_timeout": settings.job_timeout,
            "keep_result": settings.keep_result,
            "result_ttl": settings.result_ttl,
            "environment": settings.env,
        },
    )

    redis_pool = None
    try:
        # Convert redis URL to RedisSettings and create pool
        redis_settings = RedisSettings.from_dsn(WorkerConfig.redis_url)
        redis_pool = await create_pool(redis_settings)

        # Initialize worker with handle_signals=False to prevent ARQ from managing event loop
        worker = Worker(
            functions=WorkerConfig.functions,
            on_startup=WorkerConfig.on_startup,
            on_shutdown=WorkerConfig.on_shutdown,
            job_timeout=settings.job_timeout,
            keep_result=settings.keep_result,
            redis_pool=redis_pool,
            handle_signals=False,  # Critical: don't let ARQ manage signals/loop
        )

        logger.info("Worker initialized and ready to process tasks")

        # Directly await the worker's main task instead of calling worker.run()
        # This avoids the "event loop already running" error
        await worker.main()  # type: ignore[no-untyped-call]

    except Exception as e:
        logger.exception(f"Worker fatal error: {e}")
        raise
    finally:
        # Ensure Redis pool is properly closed
        if redis_pool is not None:
            try:
                await redis_pool.close()
                logger.info("Redis pool closed")
            except Exception as e:
                logger.warning(f"Error closing Redis pool: {e}")


async def main() -> None:
    """Entry point for worker process."""
    # Configure logging based on settings
    setup_logging("worker", level=settings.log_level_int)

    logger.info("Worker process starting", extra={"environment": settings.env})
    await run_worker()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker exited with error: {e}")
        sys.exit(1)
