#!/usr/bin/env python
"""Initialize database tables."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
import os


async def init_db():
    """Initialize database tables."""
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    
    # Create async engine
    engine = create_async_engine(database_url, echo=False)
    
    # Import models to register them with SQLModel.metadata
    from src.models.task import Task  # noqa: F401
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(SQLModel.metadata.create_all)
        print("✅ Database tables created successfully")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
