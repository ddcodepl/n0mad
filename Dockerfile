# Multi-stage Docker build for Nomad - Notion Task Automation
# Stage 1: Node.js build environment for JavaScript components
FROM node:20-alpine as node-builder

# Set working directory for Node.js build
WORKDIR /build

# Copy Node.js package files
COPY package*.json ./

# Install Node.js dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy JavaScript source files
COPY process-tasks.js ./

# Stage 2: Python build environment
FROM python:3.11-slim as python-builder

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy Python dependency files
COPY requirements.txt pyproject.toml ./

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy application source code
COPY . .

# Install the application in editable mode
RUN pip install -e .

# Stage 3: Final runtime stage
FROM python:3.11-slim as runtime

# Set metadata
LABEL org.opencontainers.image.title="Nomad - Notion Task Automation" \
      org.opencontainers.image.description="AI-powered Notion task refinement and automation tool" \
      org.opencontainers.image.version="0.2.0" \
      org.opencontainers.image.vendor="Nomad Development Team"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    PATH="/opt/venv/bin:$PATH" \
    NOMAD_DOCKER_ENV=1

# Install runtime system dependencies and Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    procps \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Copy Python virtual environment from builder stage
COPY --from=python-builder /opt/venv /opt/venv

# Copy Node.js dependencies from node-builder stage
COPY --from=node-builder /build/node_modules ./node_modules
COPY --from=node-builder /build/package*.json ./

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/tasks /app/data /app/.taskmaster && \
    chown -R appuser:appuser /app

# Copy Node.js process file
COPY --from=node-builder /build/process-tasks.js ./

# Switch to non-root user
USER appuser

# Create health check script
RUN echo '#!/bin/bash\npython3 -c "from entry.main import main; print(\"Health check passed\")" && echo "OK"' > /app/healthcheck.sh && \
    chmod +x /app/healthcheck.sh

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /app/healthcheck.sh

# Expose port for potential web interface or health checks
EXPOSE 8080

# Default command - run in continuous polling mode
CMD ["python3", "-m", "entry.main"]

# Alternative entry points for different modes
# CMD ["python3", "-m", "entry.main", "--refine"]     # Refine mode
# CMD ["python3", "-m", "entry.main", "--prepare"]    # Prepare mode
# CMD ["python3", "-m", "entry.main", "--queued"]     # Queued mode
# CMD ["python3", "-m", "entry.main", "--multi"]      # Multi-status mode