# ============================================================
# backend/Dockerfile — Multi-stage build for FastAPI backend
#
# ARCHITECT'S NOTE:
#   Multi-stage builds keep the final image small and secure:
#     Stage 1 (builder): installs all dependencies (including compilers)
#     Stage 2 (runtime): copies only the installed packages, not build tools
#
#   Result: a lean production image without gcc, pip cache, or build artifacts.
#   This reduces attack surface and image size (~300MB vs ~800MB).
# ============================================================

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

# Install system dependencies needed to compile some Python packages (psycopg2, cryptography)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements first for layer caching —
# Docker rebuilds from here only if requirements.txt changes, not on every code change
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Stage 2: Runtime ----
FROM python:3.11-slim AS runtime

# Install only runtime system deps (no compilers)
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user — running as root in a container is a security risk
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port (documentation only — docker-compose maps the actual port)
EXPOSE 8000

# Health check — Docker monitors this and restarts the container if it fails
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Start Uvicorn
# --workers 4: use 4 worker processes (tune to CPU cores)
# --host 0.0.0.0: listen on all interfaces (required inside Docker)
# --no-access-log: in production, access logs go through the nginx reverse proxy
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
