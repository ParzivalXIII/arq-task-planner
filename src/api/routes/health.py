"""Health check and diagnostics endpoints."""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.task import HealthCheckResponse
from src.db.session import get_session

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Check application and dependency health (database, Redis).",
)
async def health_check(session: AsyncSession = Depends(get_session)) -> HealthCheckResponse:  # noqa: B008
    """
    Health check endpoint.

    Validates connectivity to:
    - PostgreSQL/SQLite database
    - Redis (if configured)

    **Returns:**
    - Health status object with component status

    **Status Codes:**
    - 200: Application is healthy or degraded
    - 503: Critical service (database) is unavailable
    """
    db_status = "unknown"
    redis_status = None
    overall_status = "degraded"

    # Check database connectivity
    try:
        await session.execute(text("SELECT 1"))
        db_status = "healthy"
        overall_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        overall_status = "unhealthy"

    # Check Redis connectivity (if configured)
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
            r.ping()
            redis_status = "healthy"
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"
            if overall_status != "unhealthy":
                overall_status = "degraded"
    else:
        redis_status = "not_configured"

    response = HealthCheckResponse(
        status=overall_status,
        database=db_status,
        redis=redis_status,
    )

    # If database is unhealthy, raise 503 error
    if "unhealthy" in db_status:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump(),
        )

    return response
