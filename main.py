"""Application entry point."""
import logging

import uvicorn

from src.api.app import app
from src.core.config import settings
from src.observability.logging import logger as logging_logger


def main():
    """
    Run the FastAPI application using Uvicorn.
    
    Configuration is loaded from environment variables and .env file
    via the centralized settings object.
    """
    logging_logger.info(
        "Starting FastAPI application",
        extra={
            "environment": settings.env,
            "host": "0.0.0.0",
            "port": settings.app_port,
            "debug": settings.debug,
            "log_level": settings.log_level,
        },
    )
    
    # Run the server with configured settings
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.app_port,
        log_level=settings.log_level.lower(),
        reload=settings.debug,  # Auto-reload in development
    )


if __name__ == "__main__":
    main()

