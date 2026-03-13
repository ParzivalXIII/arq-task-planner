"""Alembic environment configuration."""
from logging.config import fileConfig
import os

from sqlalchemy import create_engine, pool
from alembic import context

from sqlmodel import SQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from src.models.task import Task  # noqa: F401

target_metadata = SQLModel.metadata


def _get_sync_database_url() -> str:
    """Convert async DATABASE_URL to synchronous for Alembic migrations."""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./test.db")
    
    # Convert async URLs to sync equivalents
    if "postgresql+asyncpg://" in database_url:
        return database_url.replace("postgresql+asyncpg://", "postgresql://")
    elif "sqlite+aiosqlite://" in database_url:
        return database_url.replace("sqlite+aiosqlite://", "sqlite://")
    
    return database_url


def run_migrations_online():
    """Run migrations in 'online' mode."""
    sync_url = _get_sync_database_url()
    connectable = create_engine(sync_url, poolclass=pool.NullPool)
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url") or _get_sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
