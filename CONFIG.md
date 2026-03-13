# Centralized Configuration System

## Overview

This project uses **Pydantic BaseSettings** for centralized configuration management through `src/core/config.py`. All environment variables and configuration values are managed in one place, providing:

- ✅ Type safety with Pydantic validation
- ✅ Environment-aware configuration (development, staging, production)
- ✅ Single source of truth for all settings
- ✅ Easy testing with configuration overrides
- ✅ Automatic validation and defaults

---

## Quick Start

### 1. Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` to customize settings for your environment.

### 2. Using Settings in Code

Import and use the global `settings` object:

```python
from src.core.config import settings

# Access any configuration
print(settings.database_url)
print(settings.redis_url)
print(settings.app_port)
print(settings.env)
```

---

## Configuration Sections

### APPLICATION

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_PORT` | `int` | `8000` | FastAPI application port |
| `LOG_LEVEL` | `str` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `ENV` | `str` | `development` | Environment (development, staging, production) |
| `DEBUG` | `bool` | `False` | Debug mode (auto-disabled in production) |

### DATABASE (PostgreSQL)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `POSTGRES_DB` | `str` | `task_planner` | Database name |
| `POSTGRES_USER` | `str` | `user` | Database username |
| `POSTGRES_PASSWORD` | `str` | `password` | Database password |
| `POSTGRES_HOST` | `str` | `db` | Database host |
| `POSTGRES_PORT` | `int` | `5432` | Database port |
| `DB_POOL_SIZE` | `int` | `20` | Connection pool size |
| `DB_MAX_OVERFLOW` | `int` | `10` | Connection pool overflow |
| `DB_POOL_RECYCLE` | `int` | `3600` | Connection recycle time (seconds) |

**Auto-switchable based on environment:**

- **Development**: Uses SQLite for speed (`sqlite+aiosqlite:///./dev.db`)
- **Production**: Uses PostgreSQL with asyncpg driver

### REDIS

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_HOST` | `str` | `redis` | Redis host |
| `REDIS_PORT` | `int` | `6379` | Redis port |
| `REDIS_DB` | `int` | `0` | Redis database number |
| `REDIS_PASSWORD` | `str` | `None` | Redis password (optional) |

### WORKER / ARQ

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WORKER_PROCESSES` | `int` | `4` | Worker process count |
| `WORKER_REPLICAS` | `int` | `1` | Worker replicas (Docker) |
| `JOB_TIMEOUT` | `int` | `300` | Task timeout (seconds) |
| `KEEP_RESULT` | `bool` | `True` | Keep results after completion |
| `RESULT_TTL` | `int` | `3600` | Result TTL (seconds) |

---

## Usage Patterns

### Pattern 1: Database Connection

```python
from src.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine

# Automatically selects SQLite (dev) or PostgreSQL (prod)
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
)
```

### Pattern 2: Logging Setup

```python
from src.core.config import settings
from src.observability.logging import setup_logging

# Auto-uses settings.log_level
logger = setup_logging(__name__)
```

### Pattern 3: FastAPI Server

```python
from src.core.config import settings
import uvicorn

uvicorn.run(
    app,
    host="0.0.0.0",
    port=settings.app_port,
    log_level=settings.log_level.lower(),
    reload=settings.debug,  # Only in development
)
```

### Pattern 4: Worker Configuration

```python
from src.core.config import settings

worker = Worker(
    functions=[...],
    job_timeout=settings.job_timeout,
    keep_result=settings.keep_result,
    results_expire_after=settings.result_ttl,
)
```

### Pattern 5: Environment Detection

```python
from src.core.config import settings

if settings.is_production:
    # Production-specific logic
    pass
elif settings.is_development:
    # Development-specific logic
    pass
```

---

## Environment-Aware Configuration

### Development Mode

```bash
ENV=development
LOG_LEVEL=DEBUG
DEBUG=True
# Uses SQLite database automatically
```

### Production Mode

```bash
ENV=production
LOG_LEVEL=WARNING
DEBUG=False
POSTGRES_PASSWORD=<strong-password>
POSTGRES_HOST=prod-db-host
POSTGRES_PORT=5432
# Uses PostgreSQL with asyncpg automatically
```

---

## Validation Rules

The configuration system includes automatic validation:

| Validation | Rule | Example |
|-----------|------|---------|
| **Port Range** | 1-65535 | `APP_PORT=99999` raises error |
| **Positive Integers** | > 0 | `DB_POOL_SIZE=-1` raises error |
| **Boolean Conversion** | "true"/"false" → bool | `DEBUG=true` → `True` |
| **Environment Safety** | No debug in production | `ENV=production` + `DEBUG=true` → error |

---

## Common Tasks

### Print All Settings

Run the config module to print all settings:

```bash
uv run src/core/config.py
```

Output:

```
======================================================================
APPLICATION CONFIGURATION
======================================================================

  app_port                       = 8000
  log_level                      = INFO
  env                            = development
  ...
```

### View Configuration in Code

```bash
uv run src/core/examples.py
```

This runs comprehensive examples of using the configuration.

### Override Settings for Testing

```python
# In tests, use environment variable override
import os
os.environ["LOG_LEVEL"] = "DEBUG"

from src.core.config import Settings
test_settings = Settings()  # New instance with overrides
```

---

## Best Practices

1. **Always use `settings`**, never hardcode values:

   ```python
   # ✅ GOOD
   port = settings.app_port
   
   # ❌ BAD
   port = 8000
   ```

2. **Store `.env` securely**, never commit to git:

   ```bash
   git add .env.example  # Share example
   git ignore .env       # Hide actual file
   ```

3. **Use environment-specific logic**:

   ```python
   if settings.is_production:
       # Production-safe behavior
   else:
       # Development convenience
   ```

4. **Validate early** - Pydantic does this automatically on import

5. **Document environment variables** in `.env.example`

---

## Troubleshooting

### Settings not loading from `.env`

**Solution**: Ensure `.env` is in the project root and use correct format:

```bash
# ✅ Correct
KEY=value
PASSWORD=secret123

# ❌ Incorrect
KEY = value  # Spaces around =
PASSWORD="secret123"  # Quotes (optional but allowed)
```

### Wrong database selected

**Solution**: Check `ENV` setting:

```bash
# Development: uses SQLite
ENV=development

# Production: uses PostgreSQL
ENV=production
```

### Settings not updating

**Solution**: Settings load once at import. Restart your application:

```bash
# Terminal 1: Stop the app (Ctrl+C)
# Terminal 2: Edit .env
# Terminal 3: Start the app again
```

---

## Integration with Docker Compose

The `docker-compose.yml` automatically passes environment variables:

```yaml
app:
  environment:
    - DATABASE_URL=${DATABASE_URL:-...}
    - REDIS_URL=${REDIS_URL:-...}
    - LOG_LEVEL=${LOG_LEVEL:-INFO}
```

Settings will be loaded from your `.env` file automatically.

---

## Next Steps

- Review `src/core/config.py` for full implementation
- Run `uv run src/core/examples.py` for usage examples
- Check `DOCKER_SETUP.md` for environment variable reference
- See `.env.example` for all available variables
