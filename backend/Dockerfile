FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer - only rebuilds when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage ---
FROM python:3.10-slim

WORKDIR /app

# Install only runtime system deps (no gcc needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only application code (respects .dockerignore)
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY start.sh .
RUN chmod +x start.sh

# Create non-root user
RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=8000
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["./start.sh"]
