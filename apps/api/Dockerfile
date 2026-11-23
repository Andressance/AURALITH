FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AURALITH_DATA_DIR=/data \
    AURALITH_STORAGE_DIR=/data/music

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY apps/__init__.py ./apps/__init__.py
COPY apps/api ./apps/api

EXPOSE 8000

CMD ["uvicorn", "apps.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
