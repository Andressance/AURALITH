"""Auralith API application: middleware, error handling and route wiring.

Routes live in apps/api/routers/, shared helpers in deps.py, media.py, serializers.py,
accounts.py and runtime.py, and the ORM models in models.py.
"""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, TimeoutError as DatabaseTimeoutError

from apps.api.accounts import bootstrap_owner
from apps.api.core.security import (
    get_client_ip,
    is_allowed_origin,
    SlidingWindowRateLimiter,
)
from apps.api.routers import (
    auth,
    favorites,
    health,
    jams,
    maintenance,
    playlists,
    tracks,
    users,
)
from apps.api.runtime import ALLOWED_ORIGINS, ALLOW_VERCEL_ORIGINS, SessionLocal

logger = logging.getLogger(__name__)

try:
    with SessionLocal() as db:
        bootstrap_owner(db)
except OperationalError as error:
    raise RuntimeError(
        "The database schema is missing or out of date. "
        "Run 'alembic upgrade head' before starting the API."
    ) from error

app = FastAPI(
    title="Auralith",
    version="1.2.0",
    docs_url=None if os.getenv("AURALITH_ENV", "production").lower() != "development" else "/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_origin_regex=(
        r"https://([a-zA-Z0-9-]+\.)*vercel\.app"
        if ALLOW_VERCEL_ORIGINS
        else None
    ),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    # The backup download reads the server-chosen file name from this header.
    expose_headers=["Content-Disposition"],
)
request_rate_limiter = SlidingWindowRateLimiter()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = get_client_ip(request)
    retry_after = request_rate_limiter.check(f"api:{client_ip}", limit=300, window_seconds=60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests"},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        if fetch_site == "cross-site" and not origin:
            return JSONResponse(status_code=403, content={"detail": "Cross-origin request rejected"})
        if origin:
            if not is_allowed_origin(origin, ALLOWED_ORIGINS):
                return JSONResponse(status_code=403, content={"detail": "Cross-origin request rejected"})
    response = await call_next(request)
    origin = request.headers.get("origin")
    if origin and is_allowed_origin(origin, ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'"
    if "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    if request.url.scheme == "https" or os.getenv("AURALITH_ENV", "production").lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(DatabaseTimeoutError)
async def database_pool_timeout(request: Request, error: DatabaseTimeoutError):
    logger.error("Database connection pool exhausted: %s", error)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is busy, retry shortly"},
        headers={"Retry-After": "5"},
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tracks.router)
app.include_router(playlists.router)
app.include_router(jams.router)
app.include_router(favorites.router)
app.include_router(maintenance.router)
