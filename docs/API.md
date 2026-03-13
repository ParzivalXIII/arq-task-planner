# API Documentation - Task Orchestration Service

## Overview

The API layer provides RESTful endpoints for task submission, retrieval, listing, and retry operations. All endpoints are **async-only** and fully comply with the PRD specification.

## Base URL

```
http://localhost:8000
```

## Endpoints

### 1. Submit Task (Create)

**Endpoint:** `POST /tasks`

**Description:** Create a new task and queue it for processing.

**Request Body:**

```json
{
  "task_type": "email_notification",
  "payload": {
    "email": "user@example.com",
    "subject": "Welcome"
  },
  "priority": 1,
  "max_retries": 5,
  "idempotency_key": "optional-unique-key"
}
```

**Parameters:**

- `task_type` (string, required): Task category/type (1-255 chars)
- `payload` (object): JSON-serializable task data
- `priority` (integer): 0-100, default 0 (higher = more urgent)
- `max_retries` (integer): 0-10, default 3
- `idempotency_key` (string, optional): For request deduplication

**Response:** 201 Created

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "email_notification",
  "payload": {"email": "user@example.com", "subject": "Welcome"},
  "status": "PENDING",
  "retry_count": 0,
  "max_retries": 5,
  "priority": 1,
  "created_at": "2024-03-12T10:30:00",
  "updated_at": "2024-03-12T10:30:00",
  "last_error": null
}
```

**Error Responses:**

- `400 Bad Request`: Non-JSON-serializable payload or validation error
- `409 Conflict`: Idempotency key already exists

---

### 2. Get Task

**Endpoint:** `GET /tasks/{task_id}`

**Description:** Retrieve details of a specific task.

**Parameters:**

- `task_id` (UUID, path parameter): Task identifier

**Response:** 200 OK

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "email_notification",
  "payload": {"email": "user@example.com"},
  "status": "PROCESSING",
  "retry_count": 0,
  "max_retries": 5,
  "priority": 1,
  "created_at": "2024-03-12T10:30:00",
  "updated_at": "2024-03-12T10:31:00",
  "last_error": null
}
```

**Error Responses:**

- `404 Not Found`: Task does not exist
- `422 Unprocessable Entity`: Invalid UUID format

---

### 3. List Tasks

**Endpoint:** `GET /tasks`

**Description:** Retrieve a list of tasks with optional status filtering.

**Query Parameters:**

- `status` (string, optional): Filter by status
  - Valid values: `PENDING`, `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`, `RETRYING`, `DEAD_LETTER`

**Examples:**

- `GET /tasks` - All tasks
- `GET /tasks?status=PENDING` - Only pending tasks
- `GET /tasks?status=COMPLETED` - Only completed tasks

**Response:** 200 OK

```json
{
  "tasks": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "task_type": "email_notification",
      "payload": {"email": "user@example.com"},
      "status": "PENDING",
      "retry_count": 0,
      "max_retries": 5,
      "priority": 1,
      "created_at": "2024-03-12T10:30:00",
      "updated_at": "2024-03-12T10:30:00",
      "last_error": null
    }
  ],
  "count": 1
}
```

---

### 4. Retry Task

**Endpoint:** `POST /tasks/{task_id}/retry`

**Description:** Manually retry a failed or dead-lettered task.

**Parameters:**

- `task_id` (UUID, path parameter): Task identifier

**Response:** 200 OK

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "email_notification",
  "payload": {"email": "user@example.com"},
  "status": "RETRYING",
  "retry_count": 1,
  "max_retries": 5,
  "priority": 1,
  "created_at": "2024-03-12T10:30:00",
  "updated_at": "2024-03-12T10:32:00",
  "last_error": null
}
```

**Behavior:**

- Increments `retry_count`
- Sets status to `RETRYING` if retries available
- Sets status to `DEAD_LETTER` if max retries exceeded
- Republishes task event to Redis queue

**Error Responses:**

- `404 Not Found`: Task does not exist
- `422 Unprocessable Entity`: Invalid UUID format

---

### 5. Health Check

**Endpoint:** `GET /health`

**Description:** Check application and dependency health (database, Redis).

**Response:** 200 OK

```json
{
  "status": "healthy",
  "database": "healthy",
  "redis": "healthy"
}
```

**Response (Degraded):** 200 OK

```json
{
  "status": "degraded",
  "database": "healthy",
  "redis": "not_configured"
}
```

**Response (Unhealthy):** 503 Service Unavailable

```json
{
  "status": "unhealthy",
  "database": "unhealthy: connection failed",
  "redis": "not_configured"
}
```

**Status Meanings:**

- `healthy`: All critical services are operational
- `degraded`: Primary service OK, optional service unavailable
- `unhealthy`: Critical service (database) unavailable

---

## Task Status Flow

```
PENDING → QUEUED → PROCESSING → COMPLETED
                 ↓
                FAILED/RETRYING → QUEUED → ...
                            ↓
                       DEAD_LETTER
```

**Status Descriptions:**

- `PENDING`: Task created, awaiting processing
- `QUEUED`: Task queued in Redis for worker pickup
- `PROCESSING`: Worker actively processing
- `COMPLETED`: Task completed successfully
- `FAILED`: Task execution failed
- `RETRYING`: Task marked for retry after failure
- `DEAD_LETTER`: Exceeded max retries, manual intervention needed

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "payload must be JSON serializable"
}
```

### 404 Not Found

```json
{
  "detail": "Task not found"
}
```

### 409 Conflict

```json
{
  "detail": "Task with idempotency_key already exists: unique-key-123"
}
```

### 422 Unprocessable Entity

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "priority"],
      "msg": "Input should be less than or equal to 100",
      "input": 150
    }
  ]
}
```

### 503 Service Unavailable

```json
{
  "status": "unhealthy",
  "database": "unhealthy: connection failed",
  "redis": null
}
```

---

## Implementation Details

### Dependency Injection

All endpoints use FastAPI's dependency injection for clean separation of concerns:

```python
@router.get("/tasks/{task_id}")
async def get_task(
    task_id: UUID,
    task_service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    ...
```

### Idempotency

The `idempotency_key` parameter enables idempotent task creation. If a request with the same `idempotency_key` is submitted twice, the same task is returned:

```python
# First request
POST /tasks {
  "task_type": "webhook",
  "idempotency_key": "webhook-123"
}
→ Returns task with ID "abc-123"

# Second request with same key
POST /tasks {
  "task_type": "webhook",
  "idempotency_key": "webhook-123"
}
→ Returns same task with ID "abc-123" (no duplicate created)
```

### Validation

All input is validated using Pydantic schemas:

- **Priority**: 0-100 (inclusive)
- **Max Retries**: 0-10 (inclusive)
- **Task Type**: 1-255 characters
- **Payload**: Must be JSON-serializable
- **Idempotency Key**: Optional, max 255 characters

Validation errors return HTTP 422 with detailed error information.

---

## Testing

Run all tests:

```bash
uv run pytest tests/ -v
```

Run specific test category:

```bash
uv run pytest tests/integration/ -v  # Integration tests
uv run pytest tests/unit/ -v         # Unit tests
```

Run with coverage:

```bash
uv run pytest tests/ --cov=src --cov-report=html
```

---

## Deployment

### Docker

See [Dockerfile](../../Dockerfile) and [docker-compose.yml](../../docker-compose.yml) for containerized deployment.

### Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (default: sqlite:///)
- `REDIS_URL`: Redis connection string (optional)

### Health Endpoint Monitoring

Monitor application health with:

```bash
curl http://localhost:8000/health
```

Integration with load balancers:

- Healthy: HTTP 200
- Degraded: HTTP 200 (with status="degraded")
- Unhealthy: HTTP 503

---

## Performance Considerations

- All endpoints are async for high throughput
- Task submission is O(1) with indexed lookups
- List operations support status filtering for efficient queries
- Idempotency keys use unique database constraint
- Connection pooling for database and Redis

---

## Version

API Version: 1.0.0
