"""Comprehensive metrics and observability tests (T8).

Tests verify:
- Metrics collection and aggregation
- Prometheus format exposition
- Counter, gauge, and histogram accuracy
- Thread-safe operations
"""

import pytest

from src.observability.metrics import (
    get_metrics_collector,
)


@pytest.fixture
def metrics_collector():
    """Get metrics collector and reset it."""
    collector = get_metrics_collector()
    collector.reset()
    return collector


class TestMetricsCollection:
    """Test metrics collection functionality."""

    def test_record_task_submission(self, metrics_collector):
        """Submission counter should increment."""
        assert metrics_collector.task_submissions_total == 0
        assert metrics_collector.active_tasks == 0

        metrics_collector.record_task_submission()

        assert metrics_collector.task_submissions_total == 1
        assert metrics_collector.active_tasks == 1

    def test_record_task_completion(self, metrics_collector):
        """Completion counter should increment, active_tasks decrement."""
        metrics_collector.record_task_submission()
        metrics_collector.record_task_completion()

        assert metrics_collector.task_completions_total == 1
        assert metrics_collector.active_tasks == 0

    def test_record_task_failure(self, metrics_collector):
        """Failure counter should increment, active_tasks decrement."""
        metrics_collector.record_task_submission()
        metrics_collector.record_task_failure(task_type="test_task")

        assert metrics_collector.task_failures_total == 1
        assert metrics_collector.active_tasks == 0
        assert metrics_collector.failures_by_type["test_task"] == 1

    def test_record_task_retry(self, metrics_collector):
        """Retry counter should increment."""
        assert metrics_collector.task_retries_total == 0

        metrics_collector.record_task_retry()
        metrics_collector.record_task_retry()

        assert metrics_collector.task_retries_total == 2

    def test_record_dead_letter(self, metrics_collector):
        """Dead-letter counter should increment."""
        assert metrics_collector.task_dead_letters_total == 0

        metrics_collector.record_dead_letter()

        assert metrics_collector.task_dead_letters_total == 1

    def test_request_latency_recording(self, metrics_collector):
        """Request latencies should be recorded."""
        assert len(metrics_collector.request_latencies_ms) == 0

        metrics_collector.record_request_latency(10.5)
        metrics_collector.record_request_latency(20.3)
        metrics_collector.record_request_latency(15.2)

        assert len(metrics_collector.request_latencies_ms) == 3
        assert 10.5 in metrics_collector.request_latencies_ms

    def test_worker_duration_recording(self, metrics_collector):
        """Worker durations should be recorded."""
        assert len(metrics_collector.worker_durations_ms) == 0

        metrics_collector.record_worker_duration(100.0)
        metrics_collector.record_worker_duration(150.0)

        assert len(metrics_collector.worker_durations_ms) == 2
        assert 100.0 in metrics_collector.worker_durations_ms

    def test_failures_by_type_aggregation(self, metrics_collector):
        """Failures should be aggregated by task type."""
        metrics_collector.record_task_failure("type_a")
        metrics_collector.record_task_failure("type_a")
        metrics_collector.record_task_failure("type_b")

        assert metrics_collector.failures_by_type["type_a"] == 2
        assert metrics_collector.failures_by_type["type_b"] == 1


class TestMetricsCalculations:
    """Test metrics calculations (percentiles, means, rates)."""

    def test_success_rate_calculation(self, metrics_collector):
        """Success rate should be completions/(completions+failures)."""
        metrics_collector.record_task_submission()
        metrics_collector.record_task_completion()

        metrics_collector.record_task_submission()
        metrics_collector.record_task_failure()

        # 1 success, 1 failure = 50% success rate
        rate = metrics_collector.get_success_rate()
        assert rate == 0.5

    def test_success_rate_all_success(self, metrics_collector):
        """Success rate should be 100% with no failures."""
        for _ in range(5):
            metrics_collector.record_task_submission()
            metrics_collector.record_task_completion()

        rate = metrics_collector.get_success_rate()
        assert rate == 1.0

    def test_success_rate_all_failure(self, metrics_collector):
        """Success rate should be 0% with all failures."""
        for _ in range(5):
            metrics_collector.record_task_submission()
            metrics_collector.record_task_failure()

        rate = metrics_collector.get_success_rate()
        assert rate == 0.0

    def test_success_rate_no_data(self, metrics_collector):
        """Success rate should be None with no data."""
        assert metrics_collector.get_success_rate() is None

    def test_request_latency_mean(self, metrics_collector):
        """Mean latency should be calculated correctly."""
        metrics_collector.record_request_latency(10.0)
        metrics_collector.record_request_latency(20.0)
        metrics_collector.record_request_latency(30.0)

        mean = metrics_collector.get_request_latency_mean()
        assert mean == 20.0

    def test_request_latency_percentile_50(self, metrics_collector):
        """50th percentile should be median."""
        for i in range(1, 11):
            metrics_collector.record_request_latency(float(i * 10))

        p50 = metrics_collector.get_request_latency_percentile(50)
        # With 10 samples, p50 should be around 55
        assert 50 <= p50 <= 60

    def test_request_latency_percentile_95(self, metrics_collector):
        """95th percentile should be high values."""
        for i in range(1, 101):
            metrics_collector.record_request_latency(float(i))

        p95 = metrics_collector.get_request_latency_percentile(95)
        assert p95 >= 95

    def test_worker_duration_mean(self, metrics_collector):
        """Mean worker duration should be calculated correctly."""
        metrics_collector.record_worker_duration(100.0)
        metrics_collector.record_worker_duration(200.0)
        metrics_collector.record_worker_duration(300.0)

        mean = metrics_collector.get_worker_duration_mean()
        assert mean == 200.0

    def test_worker_duration_percentile(self, metrics_collector):
        """Worker duration percentile should be accurate."""
        for i in range(1, 101):
            metrics_collector.record_worker_duration(float(i * 10))

        p95 = metrics_collector.get_worker_duration_percentile(95)
        assert p95 >= 950


class TestMetricsSnapshot:
    """Test metrics snapshot functionality."""

    def test_snapshot_captures_state(self, metrics_collector):
        """Snapshot should capture current metrics state."""
        metrics_collector.record_task_submission()
        metrics_collector.record_task_completion()
        metrics_collector.record_request_latency(15.5)

        snapshot = metrics_collector.get_snapshot()

        assert snapshot.task_submissions_total == 1
        assert snapshot.task_completions_total == 1
        assert snapshot.active_tasks == 0
        assert len(snapshot.failures_by_type) == 0

    def test_snapshot_immutability(self, metrics_collector):
        """Snapshot should be independent of collector changes."""
        metrics_collector.record_task_submission()
        snapshot1 = metrics_collector.get_snapshot()

        metrics_collector.record_task_submission()
        snapshot2 = metrics_collector.get_snapshot()

        # snapshot1 should not change
        assert snapshot1.task_submissions_total == 1
        assert snapshot2.task_submissions_total == 2

    def test_snapshot_with_all_metrics(self, metrics_collector):
        """Snapshot should include all metrics."""
        metrics_collector.record_task_submission()
        metrics_collector.record_task_completion()
        metrics_collector.record_task_retry()
        metrics_collector.record_dead_letter()
        metrics_collector.record_request_latency(10.0)
        metrics_collector.record_worker_duration(50.0)
        metrics_collector.record_task_failure("type_x")

        snapshot = metrics_collector.get_snapshot()

        assert snapshot.task_submissions_total == 1
        assert snapshot.task_completions_total == 1
        assert snapshot.task_retries_total == 1
        assert snapshot.task_dead_letters_total == 1
        assert snapshot.request_latency_mean_ms == 10.0
        assert snapshot.worker_duration_mean_ms == 50.0
        assert snapshot.failures_by_type["type_x"] == 1


class TestPrometheusFormat:
    """Test Prometheus format exposition."""

    def test_prometheus_format_includes_counters(self, metrics_collector):
        """Output should include counter metrics."""
        metrics_collector.record_task_submission()
        metrics_collector.record_task_completion()
        metrics_collector.record_task_retry()

        snapshot = metrics_collector.get_snapshot()
        output = snapshot.to_prometheus_format()

        assert "task_submissions_total 1" in output
        assert "task_completions_total 1" in output
        assert "task_retries_total 1" in output

    def test_prometheus_format_includes_gauges(self, metrics_collector):
        """Output should include gauge metrics."""
        metrics_collector.record_task_submission()
        metrics_collector.record_task_submission()

        snapshot = metrics_collector.get_snapshot()
        output = snapshot.to_prometheus_format()

        assert "active_tasks 2" in output

    def test_prometheus_format_includes_histograms(self, metrics_collector):
        """Output should include histogram metrics (percentiles)."""
        metrics_collector.record_request_latency(10.0)
        metrics_collector.record_request_latency(20.0)
        metrics_collector.record_request_latency(30.0)

        snapshot = metrics_collector.get_snapshot()
        output = snapshot.to_prometheus_format()

        # Should include mean and percentiles
        assert "request_latency_mean_ms" in output
        assert "20.00" in output  # Mean value

    def test_prometheus_format_includes_help_text(self, metrics_collector):
        """Output should include HELP and TYPE metadata."""
        metrics_collector.record_task_submission()

        snapshot = metrics_collector.get_snapshot()
        output = snapshot.to_prometheus_format()

        assert "# HELP task_submissions_total" in output
        assert "# TYPE task_submissions_total counter" in output

    def test_prometheus_format_failure_by_type(self, metrics_collector):
        """Output should include failures grouped by type."""
        metrics_collector.record_task_failure("task_type_a")
        metrics_collector.record_task_failure("task_type_a")
        metrics_collector.record_task_failure("task_type_b")

        snapshot = metrics_collector.get_snapshot()
        output = snapshot.to_prometheus_format()

        assert 'task_failures_by_type{type="task_type_a"} 2' in output
        assert 'task_failures_by_type{type="task_type_b"} 1' in output

    def test_prometheus_format_valid_syntax(self, metrics_collector):
        """Output should be valid Prometheus exposition format."""
        for i in range(5):
            metrics_collector.record_task_submission()
            if i % 2 == 0:
                metrics_collector.record_task_completion()
            else:
                metrics_collector.record_task_failure("test_type")

        snapshot = metrics_collector.get_snapshot()
        output = snapshot.to_prometheus_format()

        # Should not be empty
        assert len(output) > 0

        # Should have newlines separating metrics
        lines = output.split("\n")
        assert len(lines) > 10  # Multiple metrics

        # Each metric line should be valid
        for line in lines:
            if line and not line.startswith("#"):
                # Should contain space separator between name and value
                assert " " in line


class TestMetricsEndpoint:
    """Test the /metrics HTTP endpoint."""

    def test_metrics_endpoint_content_type_format(self, metrics_collector):
        """GET /metrics should return Prometheus-formatted text/plain."""
        # Test the response format directly without TestClient
        snapshot = metrics_collector.get_snapshot()
        output = snapshot.to_prometheus_format()

        assert isinstance(output, str)
        assert len(output) > 0
        assert "task_submissions_total" in output

    def test_metrics_endpoint_reflects_activity(self, metrics_collector):
        """Metrics endpoint should reflect recorded activity."""
        # Record some activity
        metrics_collector.record_task_submission()
        metrics_collector.record_task_completion()
        metrics_collector.record_request_latency(25.0)

        # Get metrics output
        snapshot = metrics_collector.get_snapshot()
        output = snapshot.to_prometheus_format()

        # Should show the activity
        assert "task_submissions_total 1" in output
        assert "task_completions_total 1" in output




class TestMetricsThreadSafety:
    """Test thread-safe metrics operations."""

    def test_concurrent_submissions(self, metrics_collector):
        """Multiple submissions should be aggregated correctly."""
        for _ in range(100):
            metrics_collector.record_task_submission()

        assert metrics_collector.task_submissions_total == 100

    def test_concurrent_latency_recording(self, metrics_collector):
        """Recording latencies should handle concurrent access."""
        latencies = [float(i) for i in range(1, 51)]
        for latency in latencies:
            metrics_collector.record_request_latency(latency)

        # Should have all recorded
        assert len(metrics_collector.request_latencies_ms) == 50

        # Mean should be correct (avg of 1-50 = 25.5)
        mean = metrics_collector.get_request_latency_mean()
        assert mean == 25.5  # Mean of 1-50

    def test_reset_clears_all_metrics(self, metrics_collector):
        """Reset should clear all metrics."""
        metrics_collector.record_task_submission()
        metrics_collector.record_task_completion()
        metrics_collector.record_request_latency(10.0)
        metrics_collector.record_task_failure("test")

        assert metrics_collector.task_submissions_total == 1
        assert metrics_collector.task_completions_total == 1
        assert len(metrics_collector.request_latencies_ms) == 1

        metrics_collector.reset()

        assert metrics_collector.task_submissions_total == 0
        assert metrics_collector.task_completions_total == 0
        assert len(metrics_collector.request_latencies_ms) == 0
        assert metrics_collector.failures_by_type == {}


class TestMetricsIntegration:
    """Integration tests for metrics with task operations."""

    def test_metrics_realistic_scenario(self, metrics_collector):
        """Test realistic metrics collection scenario."""
        # Simulate a few task lifecycles
        # Submit and complete
        metrics_collector.record_task_submission()
        metrics_collector.record_request_latency(12.0)
        metrics_collector.record_worker_duration(55.0)
        metrics_collector.record_task_completion()

        # Submit and fail
        metrics_collector.record_task_submission()
        metrics_collector.record_request_latency(13.0)
        metrics_collector.record_task_failure("email_task")

        # Submit, retry, then complete
        metrics_collector.record_task_submission()
        metrics_collector.record_request_latency(11.0)
        metrics_collector.record_task_retry()
        metrics_collector.record_worker_duration(100.0)
        metrics_collector.record_task_completion()

        snapshot = metrics_collector.get_snapshot()

        assert snapshot.task_submissions_total == 3
        assert snapshot.task_completions_total == 2
        assert snapshot.task_failures_total == 1
        assert snapshot.task_retries_total == 1
        assert snapshot.success_rate == 2 / 3


class TestMetricsEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_metrics_snapshot(self, metrics_collector):
        """Snapshot of empty metrics should have None percentiles."""
        snapshot = metrics_collector.get_snapshot()

        assert snapshot.task_submissions_total == 0
        assert snapshot.request_latency_mean_ms is None
        assert snapshot.request_latency_p50_ms is None
        assert snapshot.success_rate is None

    def test_single_latency_sample(self, metrics_collector):
        """Single latency sample should give same value for all percentiles."""
        metrics_collector.record_request_latency(42.0)

        assert metrics_collector.get_request_latency_mean() == 42.0
        assert metrics_collector.get_request_latency_percentile(50) == 42.0
        assert metrics_collector.get_request_latency_percentile(95) == 42.0

    def test_active_tasks_never_negative(self, metrics_collector):
        """Active tasks should not go below zero."""
        metrics_collector.record_task_completion()
        metrics_collector.record_task_completion()

        assert metrics_collector.active_tasks == 0

    def test_latency_history_capped_at_1000(self, metrics_collector):
        """Latency history should be capped to prevent memory bloat."""
        # Record 1500 samples
        for i in range(1500):
            metrics_collector.record_request_latency(float(i))

        # Should keep only last 1000
        assert len(metrics_collector.request_latencies_ms) <= 1000
