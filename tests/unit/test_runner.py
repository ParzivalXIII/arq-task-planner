"""Unit tests for worker runner."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workers.runner import run_worker


@pytest.mark.asyncio
async def test_run_worker_initialization(monkeypatch):
    """Test worker initialization with configuration."""
    # Mock the Worker class before instantiation
    mock_worker = AsyncMock()
    mock_worker.main = AsyncMock()
    mock_worker.close = AsyncMock()
    mock_worker_class = MagicMock(return_value=mock_worker)

    # Mock redis pool
    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_create_pool = AsyncMock(return_value=mock_pool)

    monkeypatch.setenv("REDIS_URL", "redis://test:6379")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    with patch("src.workers.runner.create_pool", mock_create_pool):
        with patch("src.workers.runner.Worker", mock_worker_class):
            with patch("src.observability.logging.setup_logging"):
                # Run the worker (it should initialize and then run)
                await run_worker()

                # Verify create_pool was called with redis_url
                mock_create_pool.assert_called_once()

                # Verify Worker was created with correct parameters
                mock_worker_class.assert_called_once()
                call_kwargs = mock_worker_class.call_args[1]
                assert call_kwargs["redis_pool"] == mock_pool
                assert "functions" in call_kwargs
                assert "on_startup" in call_kwargs
                assert "on_shutdown" in call_kwargs
                assert call_kwargs["handle_signals"] is False  # Should be False

                # Verify worker.main() was called
                mock_worker.main.assert_called_once()

                # Verify pool was closed
                mock_pool.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_worker_default_redis_url(monkeypatch):
    """Test worker uses default Redis URL if not set."""
    monkeypatch.delenv("REDIS_URL", raising=False)

    mock_worker = AsyncMock()
    mock_worker.main = AsyncMock()
    mock_worker.close = AsyncMock()
    mock_worker_class = MagicMock(return_value=mock_worker)

    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_create_pool = AsyncMock(return_value=mock_pool)

    with patch("src.workers.runner.create_pool", mock_create_pool):
        with patch("src.workers.runner.Worker", mock_worker_class):
            with patch("src.observability.logging.setup_logging"):
                await run_worker()

                # Verify create_pool was called
                mock_create_pool.assert_called_once()

                # Verify Worker was created with mock pool
                call_kwargs = mock_worker_class.call_args[1]
                assert call_kwargs["redis_pool"] == mock_pool

                # Verify pool was closed
                mock_pool.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_worker_keyboard_interrupt(monkeypatch):
    """Test worker handles keyboard interrupt by raising exception."""
    mock_worker = AsyncMock()
    mock_worker.main = AsyncMock(side_effect=KeyboardInterrupt())
    mock_worker_class = MagicMock(return_value=mock_worker)

    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_create_pool = AsyncMock(return_value=mock_pool)

    with patch("src.workers.runner.create_pool", mock_create_pool):
        with patch("src.workers.runner.Worker", mock_worker_class):
            with patch("src.observability.logging.setup_logging"):
                # KeyboardInterrupt should be caught and re-raised as normal exception
                with pytest.raises(KeyboardInterrupt):
                    await run_worker()


@pytest.mark.asyncio
async def test_run_worker_exception_handling(monkeypatch):
    """Test worker raises exceptions for fatal errors."""
    mock_worker = AsyncMock()

    # Make worker.main() raise an exception
    test_error = RuntimeError("Fatal worker error")
    mock_worker.main = AsyncMock(side_effect=test_error)
    mock_worker_class = MagicMock(return_value=mock_worker)

    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_create_pool = AsyncMock(return_value=mock_pool)

    with patch("src.workers.runner.create_pool", mock_create_pool):
        with patch("src.workers.runner.Worker", mock_worker_class):
            with patch("src.observability.logging.setup_logging"):
                # Exception should be raised from run_worker()
                with pytest.raises(RuntimeError, match="Fatal worker error"):
                    await run_worker()
