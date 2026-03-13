from datetime import datetime
from uuid import UUID

import pytest

from src.models.task import Task, TaskStatus


def test_task_defaults():
    task = Task(task_type="email.send", payload={"to": "user@example.com"})

    assert isinstance(task.id, UUID)
    assert task.task_type == "email.send"
    assert task.payload == {"to": "user@example.com"}
    assert task.status == TaskStatus.PENDING
    assert task.retry_count == 0
    assert task.max_retries == 3
    assert task.priority == 0
    assert isinstance(task.created_at, datetime)
    assert isinstance(task.updated_at, datetime)
    assert task.last_error is None
    assert task.idempotency_key is None


@pytest.mark.parametrize("status", list(TaskStatus))
def test_task_status_enum(status):
    # ensure all enum members coerce correctly
    assert TaskStatus(status.value) == status
