"""Async database engine and session utilities."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool, QueuePool

from src.core.config import settings

# Determine if using SQLite (which doesn't support pool parameters)
is_sqlite = "sqlite" in settings.database_url

# Create async engine with appropriate pooling strategy
# SQLite uses NullPool (no connection pooling) with connection timeout
# PostgreSQL uses QueuePool with configured size and overflow
engine_kwargs = {
    "echo": settings.debug,  # Only log queries in debug mode
    "pool_pre_ping": True,  # Verify connection before use
}

if is_sqlite:
    # SQLite doesn't support pool_size/max_overflow
    # Use NullPool and add connection timeout
    engine_kwargs["poolclass"] = NullPool           # type: ignore[arg-type]
    engine_kwargs["connect_args"] = {"timeout": 10}         # type: ignore[arg-type]
else:
    # PostgreSQL and other databases support connection pooling
    engine_kwargs["poolclass"] = QueuePool      # type: ignore[arg-type]
    engine_kwargs["pool_size"] = settings.db_pool_size      # type: ignore[arg-type]
    engine_kwargs["max_overflow"] = settings.db_max_overflow        # type: ignore[arg-type]
    engine_kwargs["pool_recycle"] = settings.db_pool_recycle        # type: ignore[arg-type]

engine = create_async_engine(settings.database_url, **engine_kwargs)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async database session and ensure it is closed after use.

    Designed for use with FastAPI dependency injection:
        @app.get("/items")
        async def read_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
