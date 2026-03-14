"""Prometheus-style metrics collection and aggregation.

Tracks:
- Request latency (histogram)
- Worker task duration (histogram)
- Task completion/failure counts (counters)
- Active task counts (gauge)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock


@dataclass
class MetricsCollector:
    """Thread-safe metrics collector for observability."""

    # Counters (cumulative)
    task_submissions_total: int = 0
    task_completions_total: int = 0
    task_failures_total: int = 0
    task_retries_total: int = 0
    task_dead_letters_total: int = 0

    # Gauges (current state)
    active_tasks: int = 0

    # Histograms (latency data) - store as lists for percentile calculation
    request_latencies_ms: list[float] = field(default_factory=list)
    worker_durations_ms: list[float] = field(default_factory=list)

    # Failure breakdown by task type
    failures_by_type: dict[str, int] = field(default_factory=dict)

    # Lock for thread-safe operations (RLock allows reentrant locking)
    _lock: RLock = field(default_factory=RLock)

    # Metadata
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def record_task_submission(self) -> None:
        """Record a task submission."""
        with self._lock:
            self.task_submissions_total += 1
            self.active_tasks += 1

    def record_task_completion(self) -> None:
        """Record a task completion."""
        with self._lock:
            self.task_completions_total += 1
            self.active_tasks = max(0, self.active_tasks - 1)

    def record_task_failure(self, task_type: str | None=None) -> None:
        """Record a task failure."""
        with self._lock:
            self.task_failures_total += 1
            if task_type:
                self.failures_by_type[task_type] = (
                    self.failures_by_type.get(task_type, 0) + 1
                )
            self.active_tasks = max(0, self.active_tasks - 1)

    def record_task_retry(self) -> None:
        """Record a task retry."""
        with self._lock:
            self.task_retries_total += 1

    def record_dead_letter(self) -> None:
        """Record a task moved to dead letter queue."""
        with self._lock:
            self.task_dead_letters_total += 1

    def record_request_latency(self, latency_ms: float) -> None:
        """Record an HTTP request latency."""
        with self._lock:
            self.request_latencies_ms.append(latency_ms)
            # Keep only last 1000 samples to avoid unbounded growth
            if len(self.request_latencies_ms) > 1000:
                self.request_latencies_ms = self.request_latencies_ms[-1000:]

    def record_worker_duration(self, duration_ms: float) -> None:
        """Record worker task execution duration."""
        with self._lock:
            self.worker_durations_ms.append(duration_ms)
            # Keep only last 1000 samples
            if len(self.worker_durations_ms) > 1000:
                self.worker_durations_ms = self.worker_durations_ms[-1000:]

    def get_request_latency_percentile(self, percentile: int) -> float | None:
        """Get request latency at specified percentile (0-100)."""
        with self._lock:
            if not self.request_latencies_ms:
                return None

            sorted_latencies = sorted(self.request_latencies_ms)
            index = int(len(sorted_latencies) * percentile / 100)
            # Clamp to valid index
            index = min(index, len(sorted_latencies) - 1)
            return sorted_latencies[index]

    def get_request_latency_mean(self) -> float | None:
        """Get mean request latency."""
        with self._lock:
            if not self.request_latencies_ms:
                return None
            return sum(self.request_latencies_ms) / len(self.request_latencies_ms)

    def get_worker_duration_percentile(self, percentile: int) -> float | None:
        """Get worker duration at specified percentile (0-100)."""
        with self._lock:
            if not self.worker_durations_ms:
                return None

            sorted_durations = sorted(self.worker_durations_ms)
            index = int(len(sorted_durations) * percentile / 100)
            # Clamp to valid index
            index = min(index, len(sorted_durations) - 1)
            return sorted_durations[index]

    def get_worker_duration_mean(self) -> float | None:
        """Get mean worker duration."""
        with self._lock:
            if not self.worker_durations_ms:
                return None
            return sum(self.worker_durations_ms) / len(self.worker_durations_ms)

    def get_success_rate(self) -> float | None:
        """Get task success rate (0.0-1.0)."""
        with self._lock:
            total = self.task_completions_total + self.task_failures_total
            if total == 0:
                return None
            return self.task_completions_total / total

    def get_snapshot(self) -> "MetricsSnapshot":
        """Get a snapshot of current metrics."""
        with self._lock:
            return MetricsSnapshot(
                task_submissions_total=self.task_submissions_total,
                task_completions_total=self.task_completions_total,
                task_failures_total=self.task_failures_total,
                task_retries_total=self.task_retries_total,
                task_dead_letters_total=self.task_dead_letters_total,
                active_tasks=self.active_tasks,
                request_latency_mean_ms=self.get_request_latency_mean(),
                request_latency_p50_ms=self.get_request_latency_percentile(50),
                request_latency_p95_ms=self.get_request_latency_percentile(95),
                request_latency_p99_ms=self.get_request_latency_percentile(99),
                worker_duration_mean_ms=self.get_worker_duration_mean(),
                worker_duration_p50_ms=self.get_worker_duration_percentile(50),
                worker_duration_p95_ms=self.get_worker_duration_percentile(95),
                worker_duration_p99_ms=self.get_worker_duration_percentile(99),
                success_rate=self.get_success_rate(),
                failures_by_type=dict(self.failures_by_type),
                started_at=self.started_at,
            )

    def reset(self) -> None:
        """Reset all metrics (primarily for testing)."""
        with self._lock:
            self.task_submissions_total = 0
            self.task_completions_total = 0
            self.task_failures_total = 0
            self.task_retries_total = 0
            self.task_dead_letters_total = 0
            self.active_tasks = 0
            self.request_latencies_ms = []
            self.worker_durations_ms = []
            self.failures_by_type = {}
            self.started_at = datetime.now(UTC)


@dataclass
class MetricsSnapshot:
    """Immutable snapshot of metrics at a point in time."""

    task_submissions_total: int
    task_completions_total: int
    task_failures_total: int
    task_retries_total: int
    task_dead_letters_total: int
    active_tasks: int
    request_latency_mean_ms: float | None
    request_latency_p50_ms: float | None
    request_latency_p95_ms: float | None
    request_latency_p99_ms: float | None
    worker_duration_mean_ms: float | None
    worker_duration_p50_ms: float | None
    worker_duration_p95_ms: float | None
    worker_duration_p99_ms: float | None
    success_rate: float | None
    failures_by_type: dict[str, int]
    started_at: datetime

    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus exposition format."""
        lines = [
            "# HELP task_submissions_total Total number of task submissions",
            "# TYPE task_submissions_total counter",
            f"task_submissions_total {self.task_submissions_total}",
            "",
            "# HELP task_completions_total Total number of completed tasks",
            "# TYPE task_completions_total counter",
            f"task_completions_total {self.task_completions_total}",
            "",
            "# HELP task_failures_total Total number of failed tasks",
            "# TYPE task_failures_total counter",
            f"task_failures_total {self.task_failures_total}",
            "",
            "# HELP task_retries_total Total number of task retries",
            "# TYPE task_retries_total counter",
            f"task_retries_total {self.task_retries_total}",
            "",
            "# HELP task_dead_letters_total Total tasks in dead-letter queue",
            "# TYPE task_dead_letters_total counter",
            f"task_dead_letters_total {self.task_dead_letters_total}",
            "",
            "# HELP active_tasks Current number of tasks being processed",
            "# TYPE active_tasks gauge",
            f"active_tasks {self.active_tasks}",
            "",
        ]

        # Request latency metrics
        if self.request_latency_mean_ms is not None:
            lines.extend([
                "# HELP request_latency_mean_ms Mean HTTP request latency",
                "# TYPE request_latency_mean_ms gauge",
                f"request_latency_mean_ms {self.request_latency_mean_ms:.2f}",
                "",
            ])

        if self.request_latency_p50_ms is not None:
            lines.extend([
                "# HELP request_latency_p50_ms 50th percentile request latency",
                "# TYPE request_latency_p50_ms gauge",
                f"request_latency_p50_ms {self.request_latency_p50_ms:.2f}",
                "",
            ])

        if self.request_latency_p95_ms is not None:
            lines.extend([
                "# HELP request_latency_p95_ms 95th percentile request latency",
                "# TYPE request_latency_p95_ms gauge",
                f"request_latency_p95_ms {self.request_latency_p95_ms:.2f}",
                "",
            ])

        if self.request_latency_p99_ms is not None:
            lines.extend([
                "# HELP request_latency_p99_ms 99th percentile request latency",
                "# TYPE request_latency_p99_ms gauge",
                f"request_latency_p99_ms {self.request_latency_p99_ms:.2f}",
                "",
            ])

        # Worker duration metrics
        if self.worker_duration_mean_ms is not None:
            lines.extend([
                "# HELP worker_duration_mean_ms Mean worker task duration",
                "# TYPE worker_duration_mean_ms gauge",
                f"worker_duration_mean_ms {self.worker_duration_mean_ms:.2f}",
                "",
            ])

        if self.worker_duration_p95_ms is not None:
            lines.extend([
                "# HELP worker_duration_p95_ms 95th percentile worker duration",
                "# TYPE worker_duration_p95_ms gauge",
                f"worker_duration_p95_ms {self.worker_duration_p95_ms:.2f}",
                "",
            ])

        if self.worker_duration_p99_ms is not None:
            lines.extend([
                "# HELP worker_duration_p99_ms 99th percentile worker duration",
                "# TYPE worker_duration_p99_ms gauge",
                f"worker_duration_p99_ms {self.worker_duration_p99_ms:.2f}",
                "",
            ])

        # Success rate
        if self.success_rate is not None:
            lines.extend([
                "# HELP task_success_rate Task completion success rate (0-1)",
                "# TYPE task_success_rate gauge",
                f"task_success_rate {self.success_rate:.4f}",
                "",
            ])

        # Failures by type
        for task_type, count in self.failures_by_type.items():
            lines.append(
                f'task_failures_by_type{{type="{task_type}"}} {count}'
            )

        return "\n".join(lines)


# Global metrics instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics_collector
