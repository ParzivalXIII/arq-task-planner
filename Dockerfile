# ============================================
# Multi-stage Dockerfile for Task Planner
# ============================================

# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv and dependencies (cache optimized: lock file first)
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen

# ============================================
# Stage 2: Final runtime image
FROM python:3.12-slim AS final

WORKDIR /app

# Install runtime-only dependencies (curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    make \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /root/.cache/uv /home/appuser/.cache/uv
COPY --from=builder --chown=appuser:appuser /app /app

# Set working directory and switch to non-root user
WORKDIR /app
USER appuser

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.cache/uv/bin:$PATH"

# Health check - verify app is responsive
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "main.py"]
