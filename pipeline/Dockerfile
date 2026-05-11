FROM python:3.11-slim

# FFmpeg нужен для F008. Постгрес-libs для psycopg2.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Stage 1 — deps. Кэшируется до тех пор, пока не меняется pyproject.toml.
# Заглушка src/ нужна, потому что setuptools ищет пакет по `where = ["src"]`
# ещё на этапе egg_info, до COPY реального исходника на следующем слое.
COPY pyproject.toml ./
RUN mkdir -p src/nup_pipeline && touch src/nup_pipeline/__init__.py && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Stage 2 — реальный source. Не сбрасывает кэш зависимостей.
COPY src/ ./src/
COPY docs/ ./docs/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8010

# Default: API. Worker запускается через docker-compose с command override.
CMD ["uvicorn", "nup_pipeline.api.app:app", "--host", "0.0.0.0", "--port", "8010"]
