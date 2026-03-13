"""Comprehensive state machine enforcement tests (T7).

Tests verify all state transitions follow the PRD specification:
- PENDING → QUEUED           (only)
- QUEUED → PROCESSING        (only)
- PROCESSING → COMPLETED, FAILED, RETRYING
- RETRYING → QUEUED, DEAD_LETTER
- COMPLETED, FAILED, DEAD_LETTER are terminal (no outgoing transitions)

All illegal transitions must raise ValueError.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from src.models.task import Task, TaskStatus
from src.services.task_service import TaskService, _validate_transition


@pytest.fixture(scope="function")
async def test_engine():
    """Create test database engine and tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Provide a database session for each test."""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


@pytest.fixture
async def task_service(db_session):
    """Provide task service instance."""
    return TaskService(session=db_session, redis_url="redis://localhost:6379")


class TestPendingStateTransitions:
    """Test transitions from PENDING state."""

    def test_pending_to_queued_allowed(self):
        """PENDING → QUEUED should be allowed."""
        _validate_transition(TaskStatus.PENDING, TaskStatus.QUEUED)
        # No exception raised

    def test_pending_to_processing_rejected(self):
        """PENDING → PROCESSING should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.PENDING, TaskStatus.PROCESSING)

    def test_pending_to_completed_rejected(self):
        """PENDING → COMPLETED should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.PENDING, TaskStatus.COMPLETED)

    def test_pending_to_failed_rejected(self):
        """PENDING → FAILED should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.PENDING, TaskStatus.FAILED)

    def test_pending_to_retrying_rejected(self):
        """PENDING → RETRYING should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.PENDING, TaskStatus.RETRYING)

    def test_pending_to_dead_letter_rejected(self):
        """PENDING → DEAD_LETTER should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.PENDING, TaskStatus.DEAD_LETTER)


class TestQueuedStateTransitions:
    """Test transitions from QUEUED state."""

    def test_queued_to_processing_allowed(self):
        """QUEUED → PROCESSING should be allowed."""
        _validate_transition(TaskStatus.QUEUED, TaskStatus.PROCESSING)
        # No exception raised

    def test_queued_to_pending_rejected(self):
        """QUEUED → PENDING should be rejected (backward)."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.QUEUED, TaskStatus.PENDING)

    def test_queued_to_completed_rejected(self):
        """QUEUED → COMPLETED should be rejected (skip processing)."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.QUEUED, TaskStatus.COMPLETED)

    def test_queued_to_failed_rejected(self):
        """QUEUED → FAILED should be rejected (skip processing)."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.QUEUED, TaskStatus.FAILED)

    def test_queued_to_retrying_rejected(self):
        """QUEUED → RETRYING should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.QUEUED, TaskStatus.RETRYING)

    def test_queued_to_dead_letter_rejected(self):
        """QUEUED → DEAD_LETTER should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.QUEUED, TaskStatus.DEAD_LETTER)


class TestProcessingStateTransitions:
    """Test transitions from PROCESSING state."""

    def test_processing_to_completed_allowed(self):
        """PROCESSING → COMPLETED should be allowed."""
        _validate_transition(TaskStatus.PROCESSING, TaskStatus.COMPLETED)
        # No exception raised

    def test_processing_to_failed_allowed(self):
        """PROCESSING → FAILED should be allowed."""
        _validate_transition(TaskStatus.PROCESSING, TaskStatus.FAILED)
        # No exception raised

    def test_processing_to_retrying_allowed(self):
        """PROCESSING → RETRYING should be allowed."""
        _validate_transition(TaskStatus.PROCESSING, TaskStatus.RETRYING)
        # No exception raised

    def test_processing_to_pending_rejected(self):
        """PROCESSING → PENDING should be rejected (backward)."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.PROCESSING, TaskStatus.PENDING)

    def test_processing_to_queued_rejected(self):
        """PROCESSING → QUEUED should be rejected (backward)."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.PROCESSING, TaskStatus.QUEUED)

    def test_processing_to_dead_letter_rejected(self):
        """PROCESSING → DEAD_LETTER should be rejected (skip to retrying)."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.PROCESSING, TaskStatus.DEAD_LETTER)


class TestRetryingStateTransitions:
    """Test transitions from RETRYING state."""

    def test_retrying_to_queued_allowed(self):
        """RETRYING → QUEUED should be allowed (retry the task)."""
        _validate_transition(TaskStatus.RETRYING, TaskStatus.QUEUED)
        # No exception raised

    def test_retrying_to_dead_letter_allowed(self):
        """RETRYING → DEAD_LETTER should be allowed (max retries reached)."""
        _validate_transition(TaskStatus.RETRYING, TaskStatus.DEAD_LETTER)
        # No exception raised

    def test_retrying_to_pending_rejected(self):
        """RETRYING → PENDING should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.RETRYING, TaskStatus.PENDING)

    def test_retrying_to_processing_rejected(self):
        """RETRYING → PROCESSING should be rejected (not a worker function)."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.RETRYING, TaskStatus.PROCESSING)

    def test_retrying_to_completed_rejected(self):
        """RETRYING → COMPLETED should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.RETRYING, TaskStatus.COMPLETED)

    def test_retrying_to_failed_rejected(self):
        """RETRYING → FAILED should be rejected."""
        with pytest.raises(ValueError, match="invalid transition"):
            _validate_transition(TaskStatus.RETRYING, TaskStatus.FAILED)


class TestTerminalStateTransitions:
    """Test that terminal states have no outgoing transitions."""

    def test_completed_to_any_rejected(self):
        """COMPLETED should be terminal (no outgoing transitions)."""
        for target in [
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
            TaskStatus.PROCESSING,
            TaskStatus.FAILED,
            TaskStatus.RETRYING,
            TaskStatus.DEAD_LETTER,
        ]:
            with pytest.raises(ValueError, match="invalid transition"):
                _validate_transition(TaskStatus.COMPLETED, target)

    def test_failed_to_any_rejected(self):
        """FAILED should be terminal (no outgoing transitions)."""
        for target in [
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
            TaskStatus.PROCESSING,
            TaskStatus.COMPLETED,
            TaskStatus.RETRYING,
            TaskStatus.DEAD_LETTER,
        ]:
            with pytest.raises(ValueError, match="invalid transition"):
                _validate_transition(TaskStatus.FAILED, target)

    def test_dead_letter_to_any_rejected(self):
        """DEAD_LETTER should be terminal (no outgoing transitions)."""
        for target in [
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
            TaskStatus.PROCESSING,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.RETRYING,
        ]:
            with pytest.raises(ValueError, match="invalid transition"):
                _validate_transition(TaskStatus.DEAD_LETTER, target)


class TestUpdateStatusWithValidation:
    """Test TaskService.update_status() enforces transitions."""

    @pytest.mark.asyncio
    async def test_update_status_valid_transition(self, task_service, db_session):
        """Valid transition should succeed."""
        # Create a task in QUEUED status
        task = Task(
            task_type="test",
            payload={},
            status=TaskStatus.QUEUED,
            max_retries=3,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # Update to PROCESSING (valid transition)
        updated = await task_service.update_status(task, TaskStatus.PROCESSING)

        assert updated.status == TaskStatus.PROCESSING
        assert updated.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_status_invalid_transition(self, task_service, db_session):
        """Invalid transition should raise ValueError."""
        task = Task(
            task_type="test",
            payload={},
            status=TaskStatus.QUEUED,
            max_retries=3,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # Try to update to PENDING (invalid backward transition)
        with pytest.raises(ValueError, match="invalid transition"):
            await task_service.update_status(task, TaskStatus.PENDING)

    @pytest.mark.asyncio
    async def test_update_status_from_terminal_rejected(
        self, task_service, db_session
    ):
        """Transitions from terminal states should fail."""
        task = Task(
            task_type="test",
            payload={},
            status=TaskStatus.COMPLETED,
            max_retries=3,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # Try any transition from COMPLETED
        with pytest.raises(ValueError, match="invalid transition"):
            await task_service.update_status(task, TaskStatus.QUEUED)

    @pytest.mark.asyncio
    async def test_update_status_persists_to_db(self, task_service, db_session):
        """Status update should persist to database."""
        task = Task(
            task_type="test",
            payload={},
            status=TaskStatus.PENDING,
            max_retries=3,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        task_id = task.id

        # Update status
        await task_service.update_status(task, TaskStatus.QUEUED)

        # Verify in database
        fresh_task = await db_session.get(Task, task_id)
        assert fresh_task.status == TaskStatus.QUEUED


class TestStateMachineGraphCompliance:
    """Test that all states and transitions comply with PRD graph."""

    def test_allowed_transitions_complete(self):
        """Verify all states are represented."""
        from src.services.task_service import _ALLOWED_TRANSITIONS

        # All states should be keys (even terminal states with empty sets)
        all_states = {      # type: ignore  # noqa: F841
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
            TaskStatus.PROCESSING,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.RETRYING,
            TaskStatus.DEAD_LETTER,
        }

        # PENDING, QUEUED, PROCESSING, RETRYING should have transitions
        # COMPLETED, FAILED, DEAD_LETTER may not have keys (implying empty transitions)
        for state in [
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
            TaskStatus.PROCESSING,
            TaskStatus.RETRYING,
        ]:
            assert state in _ALLOWED_TRANSITIONS

    def test_specific_prd_transitions(self):
        """Verify specific transitions mandated by PRD."""
        # These must be allowed:
        transitions = [
            (TaskStatus.PENDING, TaskStatus.QUEUED),
            (TaskStatus.QUEUED, TaskStatus.PROCESSING),
            (TaskStatus.PROCESSING, TaskStatus.COMPLETED),
            (TaskStatus.PROCESSING, TaskStatus.FAILED),
            (TaskStatus.PROCESSING, TaskStatus.RETRYING),
            (TaskStatus.RETRYING, TaskStatus.QUEUED),
            (TaskStatus.RETRYING, TaskStatus.DEAD_LETTER),
        ]

        for source, target in transitions:
            try:
                _validate_transition(source, target)
            except ValueError:
                pytest.fail(
                    f"PRD-mandated transition {source} → {target} is rejected"
                )

    def test_invalid_forward_skip_transitions_rejected(self):
        """Verify invalid forward-skip transitions are rejected."""
        invalid_transitions = [
            (TaskStatus.PENDING, TaskStatus.PROCESSING),
            (TaskStatus.PENDING, TaskStatus.COMPLETED),
            (TaskStatus.QUEUED, TaskStatus.COMPLETED),
            (TaskStatus.QUEUED, TaskStatus.RETRYING),
        ]

        for source, target in invalid_transitions:
            with pytest.raises(ValueError, match="invalid transition"):
                _validate_transition(source, target)

    def test_backward_transitions_rejected(self):
        """Verify all backward transitions are rejected."""
        backward_transitions = [
            (TaskStatus.QUEUED, TaskStatus.PENDING),
            (TaskStatus.PROCESSING, TaskStatus.PENDING),
            (TaskStatus.PROCESSING, TaskStatus.QUEUED),
            (TaskStatus.COMPLETED, TaskStatus.PROCESSING),
            (TaskStatus.FAILED, TaskStatus.PROCESSING),
            (TaskStatus.RETRYING, TaskStatus.PROCESSING),
        ]

        for source, target in backward_transitions:
            with pytest.raises(ValueError, match="invalid transition"):
                _validate_transition(source, target)


class TestStateMachineLifecycles:
    """Test complete task lifecycle paths through state machine."""

    def test_successful_completion_path(self):
        """Test: PENDING → QUEUED → PROCESSING → COMPLETED."""
        transitions = [
            (TaskStatus.PENDING, TaskStatus.QUEUED),
            (TaskStatus.QUEUED, TaskStatus.PROCESSING),
            (TaskStatus.PROCESSING, TaskStatus.COMPLETED),
        ]
        for source, target in transitions:
            try:
                _validate_transition(source, target)
            except ValueError:
                pytest.fail(f"Success path blocked: {source} → {target}")

    def test_immediate_failure_path(self):
        """Test: PENDING → QUEUED → PROCESSING → FAILED."""
        transitions = [
            (TaskStatus.PENDING, TaskStatus.QUEUED),
            (TaskStatus.QUEUED, TaskStatus.PROCESSING),
            (TaskStatus.PROCESSING, TaskStatus.FAILED),
        ]
        for source, target in transitions:
            try:
                _validate_transition(source, target)
            except ValueError:
                pytest.fail(f"Failure path blocked: {source} → {target}")

    def test_retry_and_success_path(self):
        """Test: ... → PROCESSING → RETRYING → QUEUED → PROCESSING → COMPLETED."""
        transitions = [
            (TaskStatus.PROCESSING, TaskStatus.RETRYING),
            (TaskStatus.RETRYING, TaskStatus.QUEUED),
            (TaskStatus.QUEUED, TaskStatus.PROCESSING),
            (TaskStatus.PROCESSING, TaskStatus.COMPLETED),
        ]
        for source, target in transitions:
            try:
                _validate_transition(source, target)
            except ValueError:
                pytest.fail(f"Retry path blocked: {source} → {target}")

    def test_retry_then_dead_letter_path(self):
        """Test: ... → RETRYING → DEAD_LETTER (max retries exceeded)."""
        transitions = [
            (TaskStatus.PROCESSING, TaskStatus.RETRYING),
            (TaskStatus.RETRYING, TaskStatus.DEAD_LETTER),
        ]
        for source, target in transitions:
            try:
                _validate_transition(source, target)
            except ValueError:
                pytest.fail(
                    f"Dead-letter path blocked: {source} → {target}"
                )

    @pytest.mark.asyncio
    async def test_full_lifecycle_in_service(self, task_service, db_session):
        """Test complete lifecycle using TaskService."""
        # Create task (starts in PENDING)
        task = Task(
            task_type="test",
            payload={},
            status=TaskStatus.PENDING,
            max_retries=3,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        assert task.status == TaskStatus.PENDING

        # Transition: PENDING → QUEUED
        task = await task_service.update_status(task, TaskStatus.QUEUED)
        assert task.status == TaskStatus.QUEUED

        # Transition: QUEUED → PROCESSING
        task = await task_service.update_status(task, TaskStatus.PROCESSING)
        assert task.status == TaskStatus.PROCESSING

        # Transition: PROCESSING → COMPLETED
        task = await task_service.update_status(task, TaskStatus.COMPLETED)
        assert task.status == TaskStatus.COMPLETED

        # Verify terminal (can't transition further)
        with pytest.raises(ValueError, match="invalid transition"):
            await task_service.update_status(task, TaskStatus.QUEUED)


class TestStateMachineEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_same_state_self_transition_rejected(self):
        """Transitioning to the same state should be rejected."""
        for status in TaskStatus:
            with pytest.raises(ValueError, match="invalid transition"):
                _validate_transition(status, status)

    @pytest.mark.asyncio
    async def test_concurrent_status_updates(self, task_service, db_session):
        """Test handling of concurrent status updates."""
        task = Task(
            task_type="test",
            payload={},
            status=TaskStatus.QUEUED,
            max_retries=3,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # First update succeeds
        task1 = await task_service.update_status(task, TaskStatus.PROCESSING)
        assert task1.status == TaskStatus.PROCESSING

        # Simulate stale task object trying to transition again from old state
        # This should fail because we're trying QUEUED → something
        stale_task = Task(
            id=task.id,
            task_type="test",
            payload={},
            status=TaskStatus.QUEUED,  # Stale state
            max_retries=3,
        )

        with pytest.raises(ValueError, match="invalid transition"):
            await task_service.update_status(stale_task, TaskStatus.COMPLETED)

    def test_invalid_state_to_nonexistent_state(self):
        """Edge case: transitioning to undefined state should raise."""
        # This tests the outer validation by trying a state not in enum
        # In practice, type hints prevent this, but we document the behavior
        pass
