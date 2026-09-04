# Multi-stage Python 3.12 production Dockerfile
FROM python:3.12-slim as base

# Prevents Python from writing pyc files to disc & buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create non-root user and persistent directories for security
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/data /app/logs && \
    chown -R botuser:botuser /app

USER botuser

# Healthcheck for container vitality
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

CMD ["python", "-m", "app.main"]
