"""Retry configuration and policy management for task execution.

This module provides configurable retry policies that ensure:
- Exponential backoff strategies
- Max retry enforcement
- Dead-letter handling
- Retry count tracking
"""

from dataclasses import dataclass
from enum import StrEnum


class BackoffStrategy(StrEnum):
    """Supported backoff strategies for retry logic."""

    EXPONENTIAL = "exponential"  # 2^retry_count
    LINEAR = "linear"  # retry_count * base_delay
    FIXED = "fixed"  # constant delay


@dataclass
class RetryPolicy:
    """Configuration for task retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts before dead-lettering.
        backoff_strategy: Strategy for calculating retry delays.
        base_delay: Base delay in seconds for backoff calculations.
        max_delay: Maximum delay in seconds to cap exponential growth.

    Example:
        >>> policy = RetryPolicy(max_retries=3, backoff_strategy=BackoffStrategy.EXPONENTIAL)
        >>> delay_for_retry_1 = policy.get_retry_delay(1)  # 2^1 = 2 seconds
        >>> delay_for_retry_2 = policy.get_retry_delay(2)  # 2^2 = 4 seconds
    """

    max_retries: int = 3
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay: int = 1
    max_delay: int = 3600  # 1 hour

    def __post_init__(self):
        """Validate retry policy configuration."""
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.base_delay <= 0:
            raise ValueError("base_delay must be > 0")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")

    def should_retry(self, retry_count: int) -> bool:
        """Check if a task should be retried based on current attempt count.

        Parameters:
            retry_count: Current number of retry attempts (0-indexed).

        Returns:
            bool: True if task should be retried, False if should be dead-lettered.
        """
        return retry_count < self.max_retries

    def get_retry_delay(self, retry_count: int) -> int:
        """Calculate the delay in seconds before the next retry attempt.

        The delay is calculated based on the configured backoff strategy:
        - EXPONENTIAL: 2^retry_count seconds (capped at max_delay)
        - LINEAR: retry_count * base_delay seconds (capped at max_delay)
        - FIXED: base_delay seconds

        Parameters:
            retry_count: Number of retries already attempted (0-indexed).

        Returns:
            int: Delay in seconds before next retry.

        Raises:
            ValueError: If retry_count is negative.
        """
        if retry_count < 0:
            raise ValueError("retry_count must be >= 0")

        if self.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            # 2^retry_count, but at least 2^1 for first retry
            delay = 2 ** (retry_count + 1)
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = (retry_count + 1) * self.base_delay
        elif self.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.base_delay
        else:
            raise ValueError(f"Unknown backoff strategy: {self.backoff_strategy}")

        # Cap at max_delay
        return min(delay, self.max_delay)

    def get_next_status_after_failure(self, retry_count: int) -> str:
        """Determine task status after a failure.

        Parameters:
            retry_count: Current number of retry attempts (0-indexed).

        Returns:
            str: Either "RETRYING" or "DEAD_LETTER".
        """
        if self.should_retry(retry_count):
            return "RETRYING"
        return "DEAD_LETTER"


# Default retry policy matching PRD specification
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    base_delay=1,
    max_delay=3600,
)
