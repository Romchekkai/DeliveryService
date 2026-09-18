FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
COPY README.md ./

RUN uv sync --no-dev

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn delivery_service.presentation.main:app --host 0.0.0.0 --port 8000"]
