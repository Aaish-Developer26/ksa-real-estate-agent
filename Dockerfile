FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies for asyncpg and psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==2.4.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure Poetry for container (no venv needed in Docker)
RUN poetry config virtualenvs.create false \
    && poetry install --only=main --no-root

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY evals/ ./evals/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash agent \
    && chown -R agent:agent /app

USER agent

EXPOSE 8000
