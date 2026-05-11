FROM python:3.11-slim

# FFmpeg нужен для F008. Постгрес-libs для psycopg2.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

COPY src/ ./src/
COPY docs/ ./docs/
COPY alembic.ini ./alembic.ini 2>/dev/null || true
COPY alembic/ ./alembic/ 2>/dev/null || true

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8010

# Default: API. Worker запускается через docker-compose с command override.
CMD ["uvicorn", "nup_pipeline.api.app:app", "--host", "0.0.0.0", "--port", "8010"]
