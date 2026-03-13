# Worker Runtime Documentation

## Overview

The worker runtime is an ARQ-based async consumer that processes tasks queued by the API layer. It handles:

- **Task Consumption**: Pulls tasks from Redis queue  
- **Task Execution**: Runs task handlers based on task type
- **Retry Logic**: Implements exponential backoff with configurable max retries
- **State Management**: Updates task status through the full lifecycle
- **Error Handling**: Records errors and manages dead-letter queue

## Architecture

```
Redis Queue (FIFO)
        ↓
   ARQ Worker
        ↓
  Task Handler
        ↓
PostgreSQL (state updates)
```

## Starting the Worker

### Local Development

```bash
# Terminal 1: Start API server
uv run python main.py

# Terminal 2: Start worker
uv run python -m src.workers.runner
```

### Docker

```bash
# Using docker-compose (see docker-compose.yml)
docker-compose up

# Or manually
docker-compose up api
docker-compose up worker
```

### Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (default: sqlite:///)
- `REDIS_URL`: Redis connection string (default: redis://localhost:6379)

## Task Lifecycle

### Normal Flow

```
PENDING → QUEUED → PROCESSING → COMPLETED
```

Worker actions:

1. Fetches task from DB (still in QUEUED state)
2. Updates status to PROCESSING
3. Executes task handler
4. Updates status to COMPLETED

### Retry Flow

```
PENDING → QUEUED → PROCESSING → FAILED → RETRYING → QUEUED → ...
```

Worker actions on failure:

1. Catches exception during handler execution
2. Increments retry_count
3. Sets status to RETRYING (if retries available) or DEAD_LETTER
4. Publishes task back to Redis with backoff delay
5. Next retry executes from QUEUED state

### Dead-Letter Queue

```
... → RETRYING → DEAD_LETTER
            ↑
       (retry_count >= max_retries)
```

Tasks in DEAD_LETTER state require manual intervention:

```python
# Manually retry a dead-lettered task
POST /tasks/{task_id}/retry
```

## Configuration

### Retry Policy

The worker implements **exponential backoff**:

```python
backoff_seconds = 2 ** retry_count

# Examples:
# Retry 1: 2^1 = 2 seconds
# Retry 2: 2^2 = 4 seconds
# Retry 3: 2^3 = 8 seconds
# Retry 4: 2^4 = 16 seconds
# ...
```

### Worker Settings

In `src/workers/arq_worker.py`:

```python
job_timeout = 300          # 5 minutes max per task
keep_result = True         # Store task results
result_ttl = 3600          # Keep results for 1 hour
```

## Task Handler Development

Custom task handlers are registered in `execute_task_handler()`:

```python
async def execute_task_handler(ctx, task_id: str) -> dict:
    """Main ARQ task handler."""
    # 1. Fetch task
    task = await get_task_from_db(task_id, engine)
    
    # 2. Update status to PROCESSING
    # 3. Execute task logic
    result = await _execute_task_logic(task)
    
    # 4. Update status to COMPLETED
    # 5. Return result
```

To add task-type-specific handlers:

```python
async def handle_email_task(task: Task) -> dict:
    """Example: Email task handler."""
    email = task.payload.get("email")
    subject = task.payload.get("subject")
    # Send email logic here
    return {"email_sent": email}

async def handle_report_task(task: Task) -> dict:
    """Example: Report generation handler."""
    # Generate report logic here
    return {"report_id": "..."}
```

Then route in the handler:

```python
if task.task_type == "email_notification":
    result = await handle_email_task(task)
elif task.task_type == "report_generation":
    result = await handle_report_task(task)
```

## Monitoring

### Worker Logs

The worker outputs structured logs:

```
INFO     - 🚀 Worker starting up
INFO     - 🔄 Processing task abc-123 (type: email_notification)
INFO     - ✅ Task abc-123 completed successfully
WARNING  - ⚠️  Task def-456 moved to DEAD_LETTER (max retries exceeded)
ERROR    - ❌ Task ghi-789 failed: Connection timeout
```

### Health Check

Check worker health via API:

```bash
curl http://localhost:8000/health
```

Returns status of database and Redis (worker requires both).

### Metrics

Track worker performance:

- Tasks processed per minute
- Average task duration
- Failure rate
- Retry rate
- Dead-letter queue size

## Best Practices

### 1. Idempotent Handlers

Tasks may be executed multiple times (network failures, duplicates). Handlers must be idempotent:

```python
# GOOD: Idempotent
async def send_email(task):
    email_id = task.payload["email_id"]
    # Check if email already sent
    if already_sent(email_id):
        return {"status": "already_sent"}
    # Send email
    return {"status": "sent"}

# BAD: Not idempotent
async def send_email(task):
    # Sends duplicate emails on retry
    return await smtp_client.send(task.payload)
```

### 2. Fail Fast

Catch errors early and provide context:

```python
# GOOD: Clear error message
if not task.payload.get("email"):
    raise ValueError("Missing required field: email")

# BAD: Generic error
raise Exception("Invalid payload")
```

### 3. Structured Logging

Log with context:

```python
# GOOD
logger.info(
    "Task processing started",
    extra={
        "task_id": task.id,
        "task_type": task.task_type,
        "retry_count": task.retry_count,
    }
)

# BAD
logger.info("Starting task")
```

### 4. Resource Cleanup

Ensure resources are released:

```python
# GOOD: Using context managers
async with db_session() as session:
    # Use session
    pass  # Automatically closed

# BAD: Forgetting to close
session = db_session()
# ...
# Connection left open
```

## Testing

### Unit Tests

Test individual handler functions:

```bash
uv run pytest tests/unit/test_worker.py -v
```

### Integration Tests

Test full task lifecycle (submit → process → verify):

```bash
uv run pytest tests/integration/test_worker_integration.py -v
```

### Running Tests with Coverage

```bash
uv run pytest tests/ --cov=src --cov-report=html
```

## Troubleshooting

### Worker Not Starting

**Issue**: `ConnectionError: Failed to connect to Redis`

**Solution**:

- Verify Redis is running: `redis-cli ping`
- Check `REDIS_URL` environment variable
- Verify network connectivity

### Tasks Not Being Processed

**Issue**: Tasks stuck in QUEUED state

**Solution**:

- Check worker is running: `ps aux | grep worker`
- Check logs for errors
- Verify database connectivity
- Check if max job timeout is too short

### Tasks Going to DEAD_LETTER

**Issue**: All tasks moving to DEAD_LETTER after max retries

**Solution**:

- Check error logs for root cause
- Verify task payload is valid
- Check external service availability
- Increase max_retries if appropriate

### Memory Leaks

**Issue**: Worker memory usage continuously increasing

**Solution**:

- Enable connection pooling verification
- Check for circular references in task data
- Monitor Redis connection pool
- Verify exception handling doesn't accumulate state

## Performance Tips

### 1. Batch Processing

For better throughput, process multiple tasks in parallel:

```python
# ARQ handles this automatically with multiple workers
# docker-compose -f docker-compose.yml up --scale worker=4
```

### 2. Optimize Handler Code

- Avoid N+1 queries
- Use connection pooling
- Cache frequently accessed data
- Profile slow handlers

### 3. Monitor Task Queue Depth

```bash
redis-cli LLEN task_queue
```

If queue is growing faster than processing, add more workers.

## Additional Resources

- [ARQ Documentation](https://arq-docs.readthedocs.io/)
- [Redis Documentation](https://redis.io/documentation)
- [Async Python Best Practices](https://docs.python.org/3/library/asyncio.html)
