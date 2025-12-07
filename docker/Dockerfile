# Hubrium MCP Server Production Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HTTP_HOST=0.0.0.0 \
    HTTP_PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml poetry.lock* README.md ./

# Install dependencies only (without the project itself)
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copy application code and configuration
COPY src ./src
COPY config ./config

# Now install the project itself
RUN poetry install --no-interaction --no-ansi

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Expose HTTP port
EXPOSE 8000

# Default command runs HTTP server
CMD ["mcp-server-http"]

