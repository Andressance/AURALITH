FROM python:3.13-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY apps/api ./apps/api
ENV AURALITH_DATA_DIR=/data
ENV AURALITH_STORAGE_DIR=/data/music
EXPOSE 8000
CMD ["uvicorn", "apps.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
