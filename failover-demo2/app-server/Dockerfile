# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gcc \
    python3-dev \
    librdkafka-dev && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd -r appgroup && \
    useradd -r -g appgroup appuser

# Create the directory for Prometheus and set ownership
RUN mkdir -p /tmp/prometheus-multiproc && \
    chown appuser:appgroup /tmp/prometheus-multiproc && \
    chmod 775 /tmp/prometheus-multiproc

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Ensure everything is owned by appuser
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose application port
EXPOSE 8080

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus-multiproc

# Command to run the application (all in one line)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "120", "--worker-tmp-dir", "/dev/shm", "--log-level", "debug", "app.app:app"]