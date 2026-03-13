# Docker Compose Setup Guide

## Quick Start

### 1. Clone environment variables

```bash
cp .env.example .env
# Edit .env if needed (defaults are suitable for development)
```

### 2. Start all services

```bash
docker-compose up -d
```

### 3. Verify services are healthy

```bash
docker-compose ps
# All services should show "healthy" or "running (healthy)"
```

### 4. Run database migrations

```bash
docker exec task_planner_app uv run alembic upgrade head
```

### 5. Check application status

```bash
curl http://localhost:8000/health
```

---

## Service Descriptions

### 📊 PostgreSQL Database (`db`)

- **Image**: `postgres:15-alpine`
- **Port**: 5432 (mapped via `DB_PORT`)
- **Health Check**: Runs `pg_isready` every 10 seconds
- **Auto-restart**: Enabled
- **Resources**: Limited to 1 CPU, 512MB RAM
- **Data Persistence**: Volume `postgres_data`

### 🔴 Redis Cache (`redis`)

- **Image**: `redis:7-alpine`
- **Port**: 6379 (mapped via `REDIS_PORT`)
- **Health Check**: Runs `redis-cli ping` every 10 seconds
- **Persistence**: AOF (Append-Only File) enabled
- **Auto-restart**: Enabled
- **Resources**: Limited to 0.5 CPU, 256MB RAM
- **Data Persistence**: Volume `redis_data`

### 🚀 FastAPI Application (`app`)

- **Port**: 8000 (mapped via `APP_PORT`)
- **Health Check**: HTTP GET `/health` every 15 seconds
- **Auto-restart**: Enabled
- **Resources**: Limited to 2 CPU, 1GB RAM
- **Hot Reload**: Source code changes trigger auto-reload (development only)
- **Dependencies**: Waits for `db` and `redis` to be **healthy** before starting

### 🛠️ ARQ Worker (`worker`)

- **Instances**: Configurable via `WORKER_REPLICAS` env var
- **Processes**: Configurable via `WORKER_PROCESSES` env var
- **Auto-restart**: Enabled
- **Resources**: Limited to 2 CPU, 1GB RAM per worker
- **Dependencies**: Waits for `db` and `redis` to be **healthy** before starting

---

## Environment Variables

All environment variables can be configured in `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_DB` | `task_planner` | Database name |
| `POSTGRES_USER` | `user` | Database username |
| `POSTGRES_PASSWORD` | `password` | Database password |
| `DB_PORT` | `5432` | Host port for PostgreSQL |
| `REDIS_PORT` | `6379` | Host port for Redis |
| `APP_PORT` | `8000` | Host port for FastAPI |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING) |
| `ENV` | `development` | Environment mode |
| `WORKER_PROCESSES` | `4` | ARQ worker concurrency |
| `WORKER_REPLICAS` | `1` | Number of worker containers |
| `JOB_TIMEOUT` | `300` | Task timeout in seconds |
| `RESULT_TTL` | `3600` | Result cache time in seconds |

---

## Key Improvements Over Original

### ✅ Production-Ready Features

1. **Health Checks**
   - All services have health checks
   - `depends_on` uses `condition: service_healthy`
   - Prevents race conditions during startup

2. **Restart Policies**
   - All services auto-restart on crash
   - `unless-stopped` policy (safe for development)

3. **Resource Limits**
   - CPU and memory limits prevent runaway containers
   - Reservation ensures minimum resources available

4. **Logging**
   - JSON file logging driver
   - Max size and file rotation configured
   - Prevents disk space exhaustion

5. **Security**
   - Dockerfile runs as non-root user (`appuser`)
   - Explicit network definition
   - Labels for monitoring integrations

### 🔧 Development Experience

1. **Live Code Reload**
   - Source code volumes mounted
   - Changes reflected immediately
   - No container rebuild needed

2. **Organized Network**
   - Explicit `task_network` bridge
   - Services communicate via hostnames
   - Isolated from other docker services

3. **Data Persistence**
   - PostgreSQL data survives container restarts
   - Redis data persisted with AOF

4. **Configuration Management**
   - Use `.env` file for all settings
   - Never hardcode secrets
   - Easy switching between environments

---

## Common Commands

### View logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f worker
```

### Scale workers

```bash
docker-compose up -d --scale worker=3
```

### Stop all services

```bash
docker-compose down
```

### Stop and remove data

```bash
docker-compose down -v  # -v removes volumes
```

### Rebuild images (after dependency changes)

```bash
docker-compose build --no-cache
docker-compose up -d
```

### Execute command in running container

```bash
docker-compose exec app uv run pytest
docker-compose exec app bash
```

### Check service status

```bash
docker-compose ps
docker-compose stats
```

---

## Troubleshooting

### Services fail to start

```bash
# Check logs
docker-compose logs

# Ensure ports aren't already in use
lsof -i :8000  # Check port 8000
```

### Database won't connect

```bash
# Verify db is healthy
docker-compose exec db pg_isready

# Check database exists
docker-compose exec db psql -U user -l
```

### Redis connection issues

```bash
# Test Redis connectivity
docker-compose exec redis redis-cli ping

# Check Redis data
docker-compose exec redis redis-cli INFO
```

### Hot reload not working

```bash
# Restart app container
docker-compose restart app

# Verify volume mount
docker-compose exec app ls -la /app/src
```

---

## Production Considerations

For production deployment, update `.env`:

```env
# Change passwords
POSTGRES_PASSWORD=<strong-password>
POSTGRES_USER=<secure-user>

# Production settings
ENV=production
LOG_LEVEL=WARNING

# Increase worker replicas
WORKER_REPLICAS=4

# Adjust resource limits in docker-compose.yml
```

Consider:

- Using managed databases (AWS RDS, etc.)
- Separate Redis instance (AWS ElastiCache, etc.)
- Load balancer in front of app
- Monitoring and alerting setup
- Regular backups
- SSL/TLS configuration
