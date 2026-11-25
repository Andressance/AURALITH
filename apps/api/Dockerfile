FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AURALITH_DATA_DIR=/data \
    AURALITH_STORAGE_DIR=/data/music

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Two build contexts are supported: the repository root (apps/ plus pyproject.toml) and
# the API directory itself (requirements.txt). Both are laid out as /app/apps/api, so the
# application imports the same way everywhere. `set -e` makes a missing file fail the
# build instead of producing an image that breaks on start.
COPY . /tmp/build-context
RUN set -eu; \
    if [ -f /tmp/build-context/pyproject.toml ]; then \
      cp /tmp/build-context/pyproject.toml /app/pyproject.toml; \
      cp -R /tmp/build-context/apps /app/apps; \
      cp /tmp/build-context/alembic.ini /app/alembic.ini; \
      pip install --no-cache-dir /app; \
    elif [ -f /tmp/build-context/requirements.txt ]; then \
      mkdir -p /app/apps/api; \
      cp -R /tmp/build-context/. /app/apps/api/; \
      pip install --no-cache-dir -r /app/apps/api/requirements.txt; \
    else \
      echo "ERROR: the build context needs pyproject.toml or requirements.txt" >&2; \
      exit 1; \
    fi; \
    test -f /app/apps/api/app.py

EXPOSE 8000

CMD ["/bin/sh", "-c", "cd /app && python apps/api/migrations/run.py && uvicorn apps.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
