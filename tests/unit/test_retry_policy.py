"""Unit tests for retry policy configuration (T6).

Tests for the RetryPolicy class ensure that:
- Backoff strategies are correctly implemented
- Max retries are enforced
- Delays are properly calculated and capped
- Status transitions are correct
"""

import pytest

from src.services.retry_policy import (
    DEFAULT_RETRY_POLICY,
    BackoffStrategy,
    RetryPolicy,
)


class TestRetryPolicyValidation:
    """Test RetryPolicy initialization and validation."""

    def test_default_policy_values(self):
        """Verify default retry policy has expected values."""
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert policy.base_delay == 1
        assert policy.max_delay == 3600

    def test_custom_policy_values(self):
        """Test creating policy with custom values."""
        policy = RetryPolicy(max_retries=5, base_delay=2, max_delay=1000)
        assert policy.max_retries == 5
        assert policy.base_delay == 2
        assert policy.max_delay == 1000

    def test_invalid_negative_max_retries(self):
        """Negative max_retries should raise ValueError."""
        with pytest.raises(ValueError, match="max_retries must be >= 0"):
            RetryPolicy(max_retries=-1)

    def test_invalid_zero_base_delay(self):
        """Zero base_delay should raise ValueError."""
        with pytest.raises(ValueError, match="base_delay must be > 0"):
            RetryPolicy(base_delay=0)

    def test_invalid_max_delay_less_than_base(self):
        """max_delay < base_delay should raise ValueError."""
        with pytest.raises(ValueError, match="max_delay must be >= base_delay"):
            RetryPolicy(base_delay=100, max_delay=50)

    def test_zero_max_retries_allowed(self):
        """max_retries = 0 should be valid."""
        policy = RetryPolicy(max_retries=0)
        assert policy.max_retries == 0


class TestShouldRetry:
    """Test retry decision logic."""

    def test_should_retry_within_limit(self):
        """should_retry returns True when under max_retries."""
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(0) is True
        assert policy.should_retry(1) is True
        assert policy.should_retry(2) is True

    def test_should_retry_at_limit(self):
        """should_retry returns False at max_retries."""
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(3) is False

    def test_should_retry_exceeds_limit(self):
        """should_retry returns False when exceeding max_retries."""
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(4) is False
        assert policy.should_retry(99) is False

    def test_should_retry_zero_max(self):
        """should_retry returns False for zero max_retries."""
        policy = RetryPolicy(max_retries=0)
        assert policy.should_retry(0) is False


class TestExponentialBackoff:
    """Test exponential backoff strategy."""

    def test_exponential_backoff_sequence(self):
        """Exponential backoff should follow 2^(n+1) pattern."""
        policy = RetryPolicy(backoff_strategy=BackoffStrategy.EXPONENTIAL)

        assert policy.get_retry_delay(0) == 2  # 2^1
        assert policy.get_retry_delay(1) == 4  # 2^2
        assert policy.get_retry_delay(2) == 8  # 2^3
        assert policy.get_retry_delay(3) == 16  # 2^4
        assert policy.get_retry_delay(4) == 32  # 2^5

    def test_exponential_backoff_capped_at_max_delay(self):
        """Exponential backoff should not exceed max_delay."""
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            max_delay=100,
        )

        # These would be 512, 1024, 2048 without capping
        assert policy.get_retry_delay(8) == 100
        assert policy.get_retry_delay(9) == 100
        assert policy.get_retry_delay(100) == 100

    def test_exponential_with_custom_time_bounds(self):
        """Exponential backoff with custom max_delay."""
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            max_delay=60,
        )

        assert policy.get_retry_delay(5) == 60  # 2^6 = 64, capped to 60


class TestLinearBackoff:
    """Test linear backoff strategy."""

    def test_linear_backoff_sequence(self):
        """Linear backoff should follow (n+1) * base_delay pattern."""
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.LINEAR,
            base_delay=5,
        )

        assert policy.get_retry_delay(0) == 5  # 1 * 5
        assert policy.get_retry_delay(1) == 10  # 2 * 5
        assert policy.get_retry_delay(2) == 15  # 3 * 5
        assert policy.get_retry_delay(3) == 20  # 4 * 5

    def test_linear_backoff_capped_at_max_delay(self):
        """Linear backoff should not exceed max_delay."""
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.LINEAR,
            base_delay=100,
            max_delay=500,
        )

        assert policy.get_retry_delay(4) == 500  # 5 * 100 = 500
        assert policy.get_retry_delay(5) == 500  # 6 * 100 = 600, capped


class TestFixedBackoff:
    """Test fixed backoff strategy."""

    def test_fixed_backoff_constant_delay(self):
        """Fixed backoff should always use base_delay."""
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.FIXED,
            base_delay=30,
        )

        assert policy.get_retry_delay(0) == 30
        assert policy.get_retry_delay(1) == 30
        assert policy.get_retry_delay(10) == 30
        assert policy.get_retry_delay(100) == 30

    def test_fixed_backoff_respects_max_delay(self):
        """Fixed backoff is capped by max_delay if set lower."""
        # Note: max_delay must be >= base_delay per validation rules
        # So we test with a base_delay that doesn't exceed max_delay initially,
        # but show that it would be capped if it did
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.FIXED,
            base_delay=50,
            max_delay=50,  # Equal to base_delay
        )
        assert policy.get_retry_delay(0) == 50


class TestGetRetryDelayEdgeCases:
    """Test edge cases for delay calculation."""

    def test_negative_retry_count_raises_error(self):
        """Negative retry_count should raise ValueError."""
        policy = RetryPolicy()
        with pytest.raises(ValueError, match="retry_count must be >= 0"):
            policy.get_retry_delay(-1)

    def test_large_retry_count(self):
        """Large retry_count should be handled correctly."""
        policy = RetryPolicy(max_delay=100)
        # Should not raise, and should respect max_delay
        delay = policy.get_retry_delay(1000)
        assert delay == 100


class TestGetNextStatusAfterFailure:
    """Test status determination after task failure."""

    def test_status_retrying_within_limit(self):
        """Status should be RETRYING when retries available."""
        policy = RetryPolicy(max_retries=3)

        assert policy.get_next_status_after_failure(0) == "RETRYING"
        assert policy.get_next_status_after_failure(1) == "RETRYING"
        assert policy.get_next_status_after_failure(2) == "RETRYING"

    def test_status_dead_letter_at_limit(self):
        """Status should be DEAD_LETTER when max_retries reached."""
        policy = RetryPolicy(max_retries=3)

        assert policy.get_next_status_after_failure(3) == "DEAD_LETTER"
        assert policy.get_next_status_after_failure(4) == "DEAD_LETTER"

    def test_status_dead_letter_zero_retries(self):
        """Status should be DEAD_LETTER for zero max_retries."""
        policy = RetryPolicy(max_retries=0)

        assert policy.get_next_status_after_failure(0) == "DEAD_LETTER"


class TestDefaultRetryPolicy:
    """Test the default retry policy constant."""

    def test_default_policy_characteristics(self):
        """Default policy should match PRD specifications."""
        assert DEFAULT_RETRY_POLICY.max_retries == 3
        assert DEFAULT_RETRY_POLICY.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert DEFAULT_RETRY_POLICY.base_delay == 1
        assert DEFAULT_RETRY_POLICY.max_delay == 3600

    def test_default_policy_follows_spec(self):
        """Default policy should implement exponential backoff as per PRD."""
        # PRD specifies 2^retry_count exponential backoff
        assert DEFAULT_RETRY_POLICY.get_retry_delay(0) == 2  # 2^1
        assert DEFAULT_RETRY_POLICY.get_retry_delay(1) == 4  # 2^2
        assert DEFAULT_RETRY_POLICY.get_retry_delay(2) == 8  # 2^3


class TestRetryPolicyIntegration:
    """Integration tests for retry policy usage patterns."""

    def test_retry_lifecycle(self):
        """Test complete retry lifecycle using policy."""
        policy = RetryPolicy(max_retries=3)

        # First attempt
        assert policy.should_retry(0) is True
        assert policy.get_retry_delay(0) == 2
        assert policy.get_next_status_after_failure(0) == "RETRYING"

        # Second attempt
        assert policy.should_retry(1) is True
        assert policy.get_retry_delay(1) == 4
        assert policy.get_next_status_after_failure(1) == "RETRYING"

        # Third attempt
        assert policy.should_retry(2) is True
        assert policy.get_retry_delay(2) == 8
        assert policy.get_next_status_after_failure(2) == "RETRYING"

        # Fourth attempt (at limit)
        assert policy.should_retry(3) is False
        assert policy.get_next_status_after_failure(3) == "DEAD_LETTER"

    def test_aggressive_retry_policy(self):
        """Test aggressive policy with many retries."""
        policy = RetryPolicy(max_retries=10)
        assert policy.should_retry(9) is True
        assert policy.should_retry(10) is False

    def test_conservative_retry_policy(self):
        """Test conservative policy with few retries."""
        policy = RetryPolicy(max_retries=1)
        assert policy.should_retry(0) is True
        assert policy.should_retry(1) is False

    def test_short_timeout_policy(self):
        """Test policy that caps delays for short-lived workers."""
        policy = RetryPolicy(
            max_retries=5,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            max_delay=10,  # Cap at 10 seconds
        )

        # Without cap: 2, 4, 8, 16, 32
        # With cap:    2, 4, 8, 10, 10
        assert policy.get_retry_delay(0) == 2
        assert policy.get_retry_delay(1) == 4
        assert policy.get_retry_delay(2) == 8
        assert policy.get_retry_delay(3) == 10
        assert policy.get_retry_delay(4) == 10
