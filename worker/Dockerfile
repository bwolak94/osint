# Worker image based on Playwright with Python support
FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

# Set working directory
WORKDIR /app

# Copy dependency definitions from backend
COPY backend/pyproject.toml backend/poetry.lock* ./

# Install Python dependencies via Poetry (no virtualenv inside container)
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copy application source
COPY backend/ .

# Run as non-root user provided by the base image
USER pwuser

CMD ["celery", "-A", "src.workers.celery_app", "worker", "--loglevel=info"]
