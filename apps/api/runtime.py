"""Paths, database engine and storage provider, built once at import."""

import logging
import os
import secrets
from pathlib import Path

from apps.api.core.security import build_allowed_origins
from apps.api.infrastructure.database import SQLAlchemyDatabaseProvider
from apps.api.infrastructure.storage.factory import build_storage_provider

logger = logging.getLogger(__name__)

BASE_DIR = Path(os.getenv("AURALITH_DATA_DIR", "./data")).resolve()
BASE_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR = Path(os.getenv("AURALITH_STORAGE_DIR", BASE_DIR / "music")).resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("AURALITH_DB_URL", f"sqlite:///{BASE_DIR / 'auralith.db'}")
database = SQLAlchemyDatabaseProvider(DATABASE_URL)
engine = database.engine
SessionLocal = database.sessions
storage = build_storage_provider(STORAGE_DIR)

ALLOWED_ORIGINS = build_allowed_origins(os.getenv("AURALITH_CORS_ORIGINS", ""))
ALLOW_VERCEL_ORIGINS = os.getenv("AURALITH_ALLOW_VERCEL_ORIGINS", "false").lower() == "true"
COOKIE_SECURE = os.getenv("AURALITH_COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.getenv("AURALITH_COOKIE_SAMESITE", "lax").lower()
if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise RuntimeError("AURALITH_COOKIE_SAMESITE must be lax, strict, or none")
if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    raise RuntimeError("AURALITH_COOKIE_SAMESITE=none requires secure cookies")
INSECURE_LOCAL_COOKIES = os.getenv("AURALITH_ALLOW_INSECURE_COOKIES", "false").lower() == "true"
if not COOKIE_SECURE and not INSECURE_LOCAL_COOKIES:
    raise RuntimeError("AURALITH_COOKIE_SECURE=false requires AURALITH_ALLOW_INSECURE_COOKIES=true")

# Media elements (<img>, <audio>) cannot send an Authorization header, and the web
# client runs on another origin, so those URLs carry a short-lived HMAC signature
# instead of the session token. The session token must never appear in a URL.
MEDIA_SECRET = os.getenv("AURALITH_MEDIA_SECRET", "").strip()
if not MEDIA_SECRET:
    MEDIA_SECRET = secrets.token_urlsafe(48)
    logger.warning(
        "AURALITH_MEDIA_SECRET is not set; media URLs will stop working after a restart"
    )
MEDIA_URL_TTL_SECONDS = int(os.getenv("AURALITH_MEDIA_URL_TTL_SECONDS", str(6 * 60 * 60)))
