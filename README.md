# Distributed Task Orchestrator

This repository contains a FastAPI-based backend for a distributed task orchestration system. It includes:

- Async HTTP API for submitting and monitoring tasks
- PostgreSQL persistence via SQLModel
- Redis-based event queue with ARQ workers
- Exponential backoff retry logic and dead-letter handling
- Structured logging and health checks

## Documentation

- [API Reference](docs/API.md) - HTTP endpoint specifications and examples
- [Worker Runtime](docs/WORKER.md) - Task processing, retry policies, and handler development
- [PRD](docs/PRD.md) - Project requirements and architecture

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 15+ or SQLite
- Redis 7+
- Docker & Docker Compose (optional)

### Local Development

```bash
# 1. Install dependencies
uv sync

# 2. Set up environment
cp .env.example .env

# 3. Run migrations (if using PostgreSQL)
alembic upgrade head

# 4. Terminal 1: Start API server
uv run python main.py

# 5. Terminal 2: Start worker
uv run python -m src.workers.runner
```

### Docker Compose

```bash
# Start all services (API, Worker, DB, Redis)
docker-compose up

# Stop all services
docker-compose down
```

## Usage

### Submit a Task

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "email_notification",
    "payload": {"email": "user@example.com", "subject": "Welcome"},
    "priority": 1,
    "max_retries": 5
  }'
```

### Monitor Task Status

```bash
curl http://localhost:8000/tasks/{task_id}
```

### List Tasks

```bash
curl "http://localhost:8000/tasks?status=PENDING"
```

### Manual Retry

```bash
curl -X POST http://localhost:8000/tasks/{task_id}/retry
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Project Structure

```
src/
  api/              # FastAPI routes and schemas
  services/         # Business logic (task service)
  workers/          # ARQ worker runtime
  models/           # SQLModel database models
  db/               # Database session management
  observability/    # Logging and metrics

tests/
  unit/             # Unit tests
  integration/      # Integration tests

docs/               # Documentation
  API.md            # API specification
  WORKER.md         # Worker documentation
  PRD.md            # Project requirements

migrations/         # Alembic database migrations
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html

# Run specific test category
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
```

## Task Status Flow

```
PENDING → QUEUED → PROCESSING → COMPLETED
                 ↓
                FAILED/RETRYING* → QUEUED → ...
                            ↓
                       DEAD_LETTER*

* Automatic retry with exponential backoff
```

## Configuration

Environment variables (see `.env.example`):

- `DATABASE_URL` - PostgreSQL/SQLite connection
- `REDIS_URL` - Redis connection
- `LOG_LEVEL` - Logging verbosity
- `JOB_TIMEOUT` - Max task execution time (seconds)
