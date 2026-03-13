#!/usr/bin/env bash
# Start ARQ worker process
# Usage: ./start_worker.sh [options]

set -e

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

# Default values - when running locally, use localhost for Redis
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///./dev.db}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
APP_ENV="${APP_ENV:-development}"

# Construct REDIS_URL from components
REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/0"

echo "🚀 Starting Distributed Task Orchestrator Worker"
echo "   Environment: $APP_ENV"
echo "   Redis: $REDIS_URL"
echo "   Database: $DATABASE_URL"
echo "   Log Level: $LOG_LEVEL"
echo ""

# Start the worker
export REDIS_HOST=$REDIS_HOST
export REDIS_PORT=$REDIS_PORT
export DATABASE_URL=$DATABASE_URL
export LOG_LEVEL=$LOG_LEVEL
export APP_ENV=$APP_ENV

uv run python -m src.workers.runner
