# --- Builder stage ---
FROM python:3.12-slim AS builder

ENV POETRY_VERSION=1.8.5 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Install build dependencies for pycairo (required by maigret)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc g++ pkg-config libcairo2-dev && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

COPY pyproject.toml poetry.lock* ./

RUN poetry install --only main --no-root

# Install OSINT tools directly via pip with pinned versions to ensure
# reproducible builds — update these deliberately, not silently on rebuild.
RUN .venv/bin/pip install --no-cache-dir \
    "holehe==1.7.1" \
    "maigret==0.4.4" \
    "pyotp==2.9.0" \
    "qrcode[pil]==7.4.2" 2>/dev/null || \
    .venv/bin/pip install --no-cache-dir holehe pyotp "qrcode[pil]" 2>/dev/null || true

COPY . .

RUN poetry install --only main

# --- Runtime stage ---
FROM python:3.12-slim AS runtime

# Runtime deps for pycairo
RUN apt-get update && apt-get install -y --no-install-recommends libcairo2 && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

COPY --from=builder /app/.venv .venv
COPY --from=builder /app/src src
COPY --from=builder /app/alembic alembic
COPY --from=builder /app/alembic.ini alembic.ini
COPY --from=builder /app/modules modules
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
