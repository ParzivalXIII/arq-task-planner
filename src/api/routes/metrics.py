"""Metrics endpoint exposing Prometheus-formatted metrics."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from src.observability.metrics import get_metrics_collector

router = APIRouter(tags=["observability"])


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus metrics endpoint",
    description="Expose application metrics in Prometheus exposition format.",
)
async def metrics_endpoint() -> str:
    """
    Prometheus-compatible metrics endpoint.

    Exposes:
    - task_submissions_total: Total tasks submitted
    - task_completions_total: Total tasks completed successfully
    - task_failures_total: Total tasks failed
    - task_retries_total: Total retry attempts
    - task_dead_letters_total: Total tasks in dead-letter queue
    - active_tasks: Current tasks being processed
    - request_latency_*: HTTP request latency percentiles
    - worker_duration_*: Worker task execution duration percentiles
    - task_success_rate: Success rate (0-1)
    - task_failures_by_type: Failure counts broken down by task type

    **Returns:**
    - Prometheus-formatted text/plain response
    """
    collector = get_metrics_collector()
    snapshot = collector.get_snapshot()
    return snapshot.to_prometheus_format()
