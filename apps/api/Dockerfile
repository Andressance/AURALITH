FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AURALITH_DATA_DIR=/data \
    AURALITH_STORAGE_DIR=/data/music

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY . /tmp/build-context
RUN if [ -f /tmp/build-context/pyproject.toml ]; then \
      cp /tmp/build-context/pyproject.toml /app/pyproject.toml; \
      cp -R /tmp/build-context/apps /app/apps; \
      cp /tmp/build-context/alembic.ini /app/alembic.ini; \
      pip install --no-cache-dir /app; \
    elif [ -f /tmp/build-context/requirements.txt ]; then \
      cp -R /tmp/build-context/. /app/; \
      pip install --no-cache-dir -r /app/requirements.txt; \
    else \
      cp -R /tmp/build-context/. /app/; \
      pip install --no-cache-dir fastapi uvicorn sqlalchemy psycopg[binary] python-multipart mutagen argon2-cffi pyjwt; \
    fi

EXPOSE 8000

CMD ["/bin/sh", "-c", "cd /app && python /app/apps/api/migrations/run.py && if [ -f /app/apps/api/app.py ]; then uvicorn apps.api.app:app --host 0.0.0.0 --port ${PORT:-8000}; else uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
