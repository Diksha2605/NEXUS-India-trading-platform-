# ============================================================
#  NXIO — Dockerfile
#  Python 3.11 slim, non-root user, production ready
# ============================================================
FROM python:3.11-slim

# Metadata
LABEL maintainer="Diksha — NXIO Founder"
LABEL description="NXIO ML Algorithmic Trading Platform"

# Non-root user for security
RUN useradd --create-home --shell /bin/bash nxio
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=nxio:nxio . .

# Create data directory with correct permissions
RUN mkdir -p data && chown -R nxio:nxio data

# Switch to non-root user
USER nxio

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start server
CMD ["python", "-m", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]