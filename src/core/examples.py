"""
Configuration System - Usage Guide and Examples

This module demonstrates how to use the centralized `settings` object
from `src.core.config`.
"""

from src.core.config import settings


def example_basic_usage():
    """Example 1: Basic usage of settings in any module."""
    print("=== Example 1: Basic Usage ===")

    # Access any configuration value
    print(f"Environment: {settings.env}")
    print(f"App Port: {settings.app_port}")
    print(f"Log Level: {settings.log_level}")
    print(f"Debug Mode: {settings.debug}")
    print()


def example_database_config():
    """Example 2: Database configuration."""
    print("=== Example 2: Database Configuration ===")

    # Get database URL (auto-switches based on environment)
    print(f"Database URL: {settings.database_url}")
    print(f"Sync Database URL (for migrations): {settings.database_url_sync}")

    # Get individual database settings
    print(f"DB Host: {settings.postgres_host}")
    print(f"DB Port: {settings.postgres_port}")
    print(f"DB Name: {settings.postgres_db}")
    print(f"Pool Size: {settings.db_pool_size}")
    print(f"Max Overflow: {settings.db_max_overflow}")
    print()


def example_redis_config():
    """Example 3: Redis configuration."""
    print("=== Example 3: Redis Configuration ===")

    # Get Redis URL
    print(f"Redis URL: {settings.redis_url}")

    # Get individual Redis settings
    print(f"Redis Host: {settings.redis_host}")
    print(f"Redis Port: {settings.redis_port}")
    print(f"Redis DB: {settings.redis_db}")
    print()


def example_worker_config():
    """Example 4: Worker/ARQ configuration."""
    print("=== Example 4: Worker Configuration ===")

    print(f"Worker Processes: {settings.worker_processes}")
    print(f"Worker Replicas: {settings.worker_replicas}")
    print(f"Job Timeout: {settings.job_timeout}s")
    print(f"Keep Result: {settings.keep_result}")
    print(f"Result TTL: {settings.result_ttl}s")
    print()


def example_environment_detection():
    """Example 5: Environment detection helpers."""
    print("=== Example 5: Environment Detection ===")

    # Use helper properties for conditional logic
    if settings.is_production:
        print("Running in PRODUCTION mode")
    elif settings.is_development:
        print("Running in DEVELOPMENT mode")
    elif settings.is_testing:
        print("Running in TESTING mode")

    print(f"Debug enabled: {settings.debug}")
    print()


def example_in_database_session():
    """Example 6: Using settings in database session setup."""
    print("=== Example 6: Database Session (Real Code) ===")
    print("""
    # In src/db/session.py:
    from src.core.config import settings

    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    """)
    print()


def example_in_logging_setup():
    """Example 7: Using settings in logging setup."""
    print("=== Example 7: Logging Setup (Real Code) ===")
    print("""
    # In src/observability/logging.py:
    from src.core.config import settings

    logger = setup_logging(
        "mymodule",
        level=settings.log_level_int  # Integer log level
    )
    """)
    print()


def example_in_fastapi_main():
    """Example 8: Using settings in FastAPI main."""
    print("=== Example 8: FastAPI Main (Real Code) ===")
    print("""
    # In main.py:
    from src.core.config import settings

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.app_port,
        log_level=settings.log_level.lower(),
        reload=settings.debug,  # Only reload in development
    )
    """)
    print()


def example_in_worker():
    """Example 9: Using settings in worker."""
    print("=== Example 9: Worker Configuration (Real Code) ===")
    print("""
    # In src/workers/runner.py:
    from src.core.config import settings

    worker = Worker(
        functions=WorkerConfig.functions,
        job_timeout=settings.job_timeout,
        keep_result=settings.keep_result,
        results_expire_after=settings.result_ttl,
        redis_pool=redis_pool,
    )
    """)
    print()


def example_print_all_settings():
    """Example 10: Print all settings for debugging."""
    print("=== Example 10: Print All Settings ===")
    print(settings.model_dump_json(indent=2, exclude={"postgres_password", "redis_password"}))
    print()


if __name__ == "__main__":
    """Run all examples."""
    print("\n" + "=" * 70)
    print("CENTRALIZED CONFIGURATION - USAGE EXAMPLES")
    print("=" * 70 + "\n")

    example_basic_usage()
    example_database_config()
    example_redis_config()
    example_worker_config()
    example_environment_detection()
    example_in_database_session()
    example_in_logging_setup()
    example_in_fastapi_main()
    example_in_worker()
    example_print_all_settings()

    print("=" * 70)
    print("Run this file to see all configuration examples:")
    print("  uv run src/core/examples.py")
    print("=" * 70 + "\n")
