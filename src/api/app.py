import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from src.api.routes import health_router, tasks_router
from src.core.config import settings
from src.observability.logging import logger

app = FastAPI(
    title="Distributed Task Orchestrator",
    description="Production-grade distributed task orchestration backend",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on application startup."""
    try:
        logger.info("Initializing database tables")
        engine = create_async_engine(settings.database_url, echo=False)
        
        # Import models to register them with SQLModel.metadata
        from src.models.task import Task  # noqa: F401
        
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("Database tables initialized successfully")
        
        await engine.dispose()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


# Register routers
app.include_router(tasks_router)
app.include_router(health_router)
