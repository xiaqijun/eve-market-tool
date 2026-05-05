# ============================================================
# Production Dockerfile — EVE Market Tool
# ============================================================

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[dev]" && \
    pip install --no-cache-dir psycopg2-binary

# Copy application code
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY static/ static/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start with uvicorn (single worker — APScheduler runs in-process)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
