"""
Centralized configuration management using Pydantic BaseSettings.

This module provides a single source of truth for all application configuration,
supporting environment variables and .env files for both development and production.

Usage:
    from src.core.config import settings

    # Access configuration
    db_url = settings.database_url
    log_level = settings.log_level
    redis_url = settings.redis_url
"""

import logging
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars
    )

    # =========================================================================
    # APPLICATION
    # =========================================================================
    app_port: int = Field(
        default=8000,
        description="FastAPI app port",
        alias="APP_PORT",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
        alias="LOG_LEVEL",
    )
    env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Environment mode",
        alias="ENV",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode (should only be True in development)",
    )

    # =========================================================================
    # DATABASE (PostgreSQL)
    # =========================================================================
    postgres_db: str = Field(
        default="task_planner",
        description="PostgreSQL database name",
        alias="POSTGRES_DB",
    )
    postgres_user: str = Field(
        default="user",
        description="PostgreSQL user",
        alias="POSTGRES_USER",
    )
    postgres_password: str = Field(
        default="password",
        description="PostgreSQL password",
        alias="POSTGRES_PASSWORD",
    )
    postgres_host: str = Field(
        default="db",
        description="PostgreSQL host",
        alias="POSTGRES_HOST",
    )
    postgres_port: int = Field(
        default=5432,
        description="PostgreSQL port",
        alias="POSTGRES_PORT",
    )
    db_pool_size: int = Field(
        default=20,
        description="Database connection pool size",
        alias="DB_POOL_SIZE",
    )
    db_max_overflow: int = Field(
        default=10,
        description="Database connection pool max overflow",
        alias="DB_MAX_OVERFLOW",
    )
    db_pool_recycle: int = Field(
        default=3600,
        description="Database connection recycle time in seconds",
        alias="DB_POOL_RECYCLE",
    )

    @property
    def database_url(self) -> str:
        """Construct async PostgreSQL URL for asyncpg driver."""
        if self.env == "development":
            # Use SQLite for faster development/testing
            return "sqlite+aiosqlite:///./dev.db"
        return (
            f"postgresql+asyncpg://{self.postgres_user}"
            f":{self.postgres_password}@{self.postgres_host}"
            f":{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Construct synchronous PostgreSQL URL for Alembic migrations."""
        if self.env == "development":
            return "sqlite:///./dev.db"
        return (
            f"postgresql://{self.postgres_user}"
            f":{self.postgres_password}@{self.postgres_host}"
            f":{self.postgres_port}/{self.postgres_db}"
        )

    # =========================================================================
    # REDIS
    # =========================================================================
    redis_host: str = Field(
        default="localhost",
        description="Redis host",
        alias="REDIS_HOST",
    )
    redis_port: int = Field(
        default=6379,
        description="Redis port",
        alias="REDIS_PORT",
    )
    redis_db: int = Field(
        default=0,
        description="Redis database number",
        alias="REDIS_DB",
    )
    redis_password: str | None = Field(
        default=None,
        description="Redis password (optional)",
        alias="REDIS_PASSWORD",
    )

    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # =========================================================================
    # WORKER / ARQ
    # =========================================================================
    worker_processes: int = Field(
        default=4,
        description="Number of worker processes",
        alias="WORKER_PROCESSES",
    )
    worker_replicas: int = Field(
        default=1,
        description="Number of worker replicas (Docker Compose)",
        alias="WORKER_REPLICAS",
    )
    job_timeout: int = Field(
        default=300,
        description="Job timeout in seconds",
        alias="JOB_TIMEOUT",
    )
    keep_result: bool = Field(
        default=True,
        description="Keep results after job completion",
        alias="KEEP_RESULT",
    )
    result_ttl: int = Field(
        default=3600,
        description="Result TTL in seconds",
        alias="RESULT_TTL",
    )

    # =========================================================================
    # VALIDATION
    # =========================================================================
    @field_validator("app_port", "postgres_port", "redis_port", mode="before")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        port = int(v) if isinstance(v, str) else v
        if not 1 <= port <= 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {port}")
        return port

    @field_validator("db_pool_size", "db_max_overflow", mode="before")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """Validate positive integers."""
        val = int(v) if isinstance(v, str) else v
        if val <= 0:
            raise ValueError(f"Must be positive, got {val}")
        return val

    @field_validator("debug", mode="before")
    @classmethod
    def validate_bool(cls, v: bool | str) -> bool:
        """Convert string booleans to actual booleans."""
        if isinstance(v, bool):
            return v
        return v.lower() in ("true", "1", "yes", "on")

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str, info: ValidationInfo) -> str:
        """Warn if debug is True in production."""
        debug = info.data.get("debug", False)
        if v == "production" and debug:
            raise ValueError("debug must be False in production environment")
        return v

    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.env == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing."""
        return self.env == "testing"

    @property
    def log_level_int(self) -> int:
        """Get logging level as integer."""
        return getattr(logging, self.log_level)


# Global settings instance
settings = Settings()


# =====================================================================
# DEVELOPMENT / DEBUG UTILITIES
# =====================================================================
if __name__ == "__main__":
    """Print all settings when run as main script."""
    print("\n" + "=" * 70)
    print("APPLICATION CONFIGURATION")
    print("=" * 70 + "\n")
    for key, value in settings.model_dump().items():
        # Mask sensitive data
        display_value = (
            "***" if "password" in key.lower() else value
        )
        print(f"  {key.upper():<30} = {display_value}")
    print("\n" + "=" * 70)
    print(f"Environment: {settings.env.upper()}")
    print(f"Debug Mode: {settings.debug}")
    print(f"Database URL: {settings.database_url}")
    print(f"Redis URL: {settings.redis_url}")
    print("=" * 70 + "\n")
