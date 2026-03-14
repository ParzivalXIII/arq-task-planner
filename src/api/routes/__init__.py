"""API route modules."""
from src.api.routes.health import router as health_router
from src.api.routes.metrics import router as metrics_router
from src.api.routes.tasks import router as tasks_router

__all__ = ["health_router", "metrics_router", "tasks_router"]
