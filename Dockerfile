# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# Security: run as non-root user
RUN useradd -m appuser

# Copy application code
COPY . .

# Create source and persistent-state directories with correct ownership. On
# Railway, mount a Volume at /app/state; source PDFs remain in /app/data.
RUN mkdir -p /app/data /app/state && chown -R appuser:appuser /app

# Railway mounts a Volume after the image is built, so its runtime ownership
# cannot be fixed by the build-time chown above. The entrypoint repairs that
# ownership before dropping privileges to appuser.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh

USER root

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health')" || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
