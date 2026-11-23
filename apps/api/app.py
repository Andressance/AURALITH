import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import tempfile
import zipfile
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from mutagen import File as MutagenFile
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy import inspect, text

try:
    from apps.api.infrastructure.database import SQLAlchemyDatabaseProvider
    from apps.api.infrastructure.storage.local import LocalStorageProvider
    from apps.api.infrastructure.storage.supabase import SupabaseStorageProvider
    from apps.api.infrastructure.storage.s3 import S3StorageProvider
    from apps.api.core.security import (
        build_allowed_origins,
        is_allowed_origin,
        is_strong_owner_password,
        login_rate_limiter,
    )
except ModuleNotFoundError:
    from infrastructure.database import SQLAlchemyDatabaseProvider
    from infrastructure.storage.local import LocalStorageProvider
    from infrastructure.storage.supabase import SupabaseStorageProvider
    from infrastructure.storage.s3 import S3StorageProvider
    from core.security import (
        build_allowed_origins,
        is_allowed_origin,
        is_strong_owner_password,
        login_rate_limiter,
    )


BASE_DIR = Path(os.getenv("AURALITH_DATA_DIR", "./data")).resolve()
BASE_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR = Path(os.getenv("AURALITH_STORAGE_DIR", BASE_DIR / "music")).resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("AURALITH_DB_URL", f"sqlite:///{BASE_DIR / 'auralith.db'}")
database = SQLAlchemyDatabaseProvider(DATABASE_URL)
engine = database.engine
SessionLocal = database.sessions
storage_provider_name = os.getenv("AURALITH_STORAGE_PROVIDER", "local").lower()
if storage_provider_name == "supabase":
    storage = SupabaseStorageProvider(
        bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "music"),
    )
elif storage_provider_name == "local":
    storage = LocalStorageProvider(STORAGE_DIR)
elif storage_provider_name == "neon":
    storage = S3StorageProvider()
else:
    raise RuntimeError(
        "AURALITH_STORAGE_PROVIDER must be 'local', 'supabase', or 'neon'"
    )


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    display_name = Column(String)
    avatar_path = Column(String)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="owner", nullable=False)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    artist = Column(String)
    album = Column(String)
    year = Column(Integer)
    genre = Column(String)
    duration = Column(Integer)
    sha256 = Column(String, unique=False, nullable=False)
    file_name = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    cover_path = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Playlist(Base):
    __tablename__ = "playlists"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    cover_path = Column(String)


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"
    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    position = Column(Integer, nullable=False)


class Favorite(Base):
    __tablename__ = "favorites"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)


class Invitation(Base):
    __tablename__ = "invitations"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    display_name = Column(String)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)


Base.metadata.create_all(engine)


def ensure_optional_columns():
    columns = {
        "users": (
            ("display_name", "VARCHAR"),
            ("avatar_path", "VARCHAR"),
        ),
        "tracks": (("cover_path", "VARCHAR"),),
        "playlists": (("cover_path", "VARCHAR"),),
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, table_columns in columns.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in table_columns:
                if column_name not in existing:
                    connection.execute(
                        text(
                            f"ALTER TABLE {table_name} "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )


ensure_optional_columns()
password_hasher = PasswordHasher()
DUMMY_PASSWORD_HASH = password_hasher.hash(secrets.token_urlsafe(32))
ALLOWED_ORIGINS = build_allowed_origins(os.getenv("AURALITH_CORS_ORIGINS", ""))
COOKIE_SECURE = os.getenv("AURALITH_COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.getenv("AURALITH_COOKIE_SAMESITE", "lax").lower()
if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise RuntimeError("AURALITH_COOKIE_SAMESITE must be lax, strict, or none")
if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    raise RuntimeError("AURALITH_COOKIE_SAMESITE=none requires secure cookies")
INSECURE_LOCAL_COOKIES = os.getenv("AURALITH_ALLOW_INSECURE_COOKIES", "false").lower() == "true"
if not COOKIE_SECURE and not INSECURE_LOCAL_COOKIES:
    raise RuntimeError("AURALITH_COOKIE_SECURE=false requires AURALITH_ALLOW_INSECURE_COOKIES=true")


def db_session():
    with SessionLocal() as db:
        yield db


def bootstrap_owner(db: Session):
    owner = db.scalar(select(User).where(User.role == "owner"))
    username = os.getenv("AURALITH_OWNER_USERNAME", "owner")
    password = os.getenv("AURALITH_OWNER_PASSWORD")
    if password and not is_strong_owner_password(password):
        raise RuntimeError("AURALITH_OWNER_PASSWORD must be at least 12 characters and include lowercase, uppercase, and digits")
    if owner:
        if password and owner.password_hash == "":  # reserved for legacy rows
            owner.password_hash = password_hasher.hash(password)
            db.commit()
        elif (
            password
            and os.getenv("AURALITH_RESET_OWNER_PASSWORD", "false").lower() == "true"
        ):
            owner.password_hash = password_hasher.hash(password)
            db.commit()
        return
    if not password:
        raise RuntimeError("AURALITH_OWNER_PASSWORD must be set before the first startup")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,63}", username):
        raise RuntimeError("AURALITH_OWNER_USERNAME contains unsupported characters")
    db.add(User(username=username, password_hash=password_hasher.hash(password), role="owner"))
    db.commit()


with SessionLocal() as db:
    bootstrap_owner(db)


app = FastAPI(
    title="Auralith",
    version="0.1.0",
    docs_url=None if os.getenv("AURALITH_ENV", "production").lower() != "development" else "/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_origin_regex=r"https://([a-zA-Z0-9-]+\.)*vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
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
    response.headers["Cache-Control"] = "no-store"
    if request.url.scheme == "https" or os.getenv("AURALITH_ENV", "production").lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(
    db: Annotated[Session, Depends(db_session)],
    auralith_session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    token: str | None = None,
):
    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization[7:].strip()
    auth_token = bearer_token or auralith_session or token
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    digest = token_hash(auth_token)
    session = db.scalar(select(Session).where(Session.token_hash == digest))
    now = datetime.now(timezone.utc)
    expires_at = normalize_utc(session.expires_at) if session else now
    if not session or expires_at <= now:
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=401, detail="Session expired")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/health")
def health_alias():
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(request: Request, payload: dict, db: Annotated[Session, Depends(db_session)]):
    username = str(payload.get("username", ""))[:128]
    password = str(payload.get("password", ""))[:1024]
    forwarded = request.headers.get("x-forwarded-for")
    client_ip = (forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown"))
    if not login_rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Too many login attempts")
    user = db.scalar(select(User).where(User.username == username))
    if not user:
        try:
            password_hasher.verify(DUMMY_PASSWORD_HASH, password)
        except VerifyMismatchError:
            pass
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        password_hasher.verify(user.password_hash, password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    login_rate_limiter.reset(client_ip)
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=12)
    db.add(Session(user_id=user.id, token_hash=token_hash(token), expires_at=expires))
    db.commit()
    response = JSONResponse({"ok": True, "token": token})
    response.set_cookie(
        "auralith_session",
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=12 * 60 * 60,
    )
    return response


@app.post("/api/auth/logout")
def logout(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
    auralith_session: Annotated[str | None, Cookie()] = None,
):
    if auralith_session:
        db.query(Session).filter(Session.token_hash == token_hash(auralith_session)).delete()
        db.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie("auralith_session")
    return response


@app.post("/api/auth/password")
def change_password(
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    current_password = str(payload.get("current_password", ""))
    new_password = str(payload.get("new_password", ""))
    try:
        password_hasher.verify(user.password_hash, current_password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if len(new_password) < 12:
        raise HTTPException(status_code=400, detail="New password must contain at least 12 characters")
    if not is_strong_owner_password(new_password):
        raise HTTPException(status_code=400, detail="New password must include lowercase, uppercase, and digits")
    user.password_hash = password_hasher.hash(new_password)
    db.commit()
    return {"ok": True}


@app.post("/api/auth/logout-all")
def logout_all(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    db.query(Session).filter(Session.user_id == user.id).delete()
    db.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie("auralith_session")
    return response


@app.get("/api/me")
def me(user: Annotated[User, Depends(current_user)]):
    return {
        "id": user.id,
        "username": user.username,
        "display_name": getattr(user, "display_name", None) or user.username,
        "role": user.role,
        "avatar_url": f"/api/profile/avatar" if getattr(user, "avatar_path", None) else None,
    }


def require_owner(user: User):
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")


@app.get("/api/owner/invitations")
def list_invitations(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    require_owner(user)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    invitations = db.scalars(
        select(Invitation).order_by(Invitation.id.desc())
    ).all()
    return [
        {
            "id": invitation.id,
            "code": invitation.code,
            "display_name": invitation.display_name,
            "expires_at": invitation.expires_at.isoformat(),
            "used": invitation.used_at is not None,
        }
        for invitation in invitations
        if invitation.expires_at > now
    ]


@app.post("/api/owner/invitations")
def create_invitation(
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    require_owner(user)
    display_name = str(payload.get("display_name") or "").strip()[:100]
    code = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)
    invitation = Invitation(
        code=code,
        display_name=display_name or None,
        created_by=user.id,
        expires_at=expires_at,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return {
        "code": code,
        "display_name": invitation.display_name,
        "expires_at": invitation.expires_at.isoformat(),
    }


@app.post("/api/invitations/{code}/activate")
def activate_invitation(
    code: str,
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
):
    invitation = db.scalar(select(Invitation).where(Invitation.code == code))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not invitation or invitation.used_at or invitation.expires_at <= now:
        raise HTTPException(status_code=410, detail="Invitation is invalid or expired")
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    display_name = str(payload.get("display_name") or invitation.display_name or "").strip()[:100]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,63}", username):
        raise HTTPException(status_code=400, detail="Username contains unsupported characters")
    if not is_strong_owner_password(password):
        raise HTTPException(status_code=400, detail="Password must contain lowercase, uppercase and digits")
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="Username is already in use")
    invited = User(
        username=username,
        display_name=display_name or None,
        password_hash=password_hasher.hash(password),
        role="guest",
    )
    db.add(invited)
    invitation.used_at = now
    db.commit()
    db.refresh(invited)
    return {"ok": True, "username": invited.username, "role": invited.role}


@app.post("/api/profile")
async def update_profile(
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    display_name = str(payload.get("display_name") or "").strip()[:100]
    username = str(payload.get("username") or user.username).strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,63}", username):
        raise HTTPException(status_code=400, detail="Username contains unsupported characters")
    existing = db.scalar(select(User).where(User.username == username, User.id != user.id))
    if existing:
        raise HTTPException(status_code=409, detail="Username is already in use")
    user.username = username
    user.display_name = display_name or None
    db.commit()
    db.refresh(user)
    return me(user)


@app.post("/api/profile/avatar")
async def update_profile_avatar(
    file: UploadFile,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    return await update_avatar(file, db, user)


@app.get("/api/profile/avatar")
def profile_avatar(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    return image_response(getattr(user, "avatar_path", None), "Avatar not found")


async def update_avatar(file: UploadFile, db: Session, user: User):
    path, content_type = await upload_profile_image(file, f"avatars/{user.id}")
    user.avatar_path = path
    db.commit()
    return {"avatar_url": "/api/profile/avatar", "content_type": content_type}


async def upload_profile_image(file: UploadFile, key_prefix: str) -> tuple[str, str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only JPG, PNG and WebP images are supported")
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 5 MB")
    content_type = ALLOWED_IMAGE_SUFFIXES[suffix]
    if content_type == "image/jpeg" and not (content.startswith(b"\xff\xd8\xff")):
        raise HTTPException(status_code=400, detail="Invalid JPEG image")
    if content_type == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="Invalid PNG image")
    if content_type == "image/webp" and not (len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"):
        raise HTTPException(status_code=400, detail="Invalid WebP image")
    path = f"{key_prefix}{suffix}"
    storage.upload(path, content, content_type)
    return path, content_type


def image_response(path: str | None, not_found: str):
    if not path:
        raise HTTPException(status_code=404, detail=not_found)
    try:
        suffix = Path(path).suffix.lower()
        media_type = ALLOWED_IMAGE_SUFFIXES.get(suffix, "application/octet-stream")
        source = storage.open(path)
        return StreamingResponse(
            source,
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=86400"},
        )
    except Exception as error:
        raise HTTPException(status_code=404, detail=not_found) from error


ALLOWED_SUFFIXES = {".mp3": "audio/mpeg", ".flac": "audio/flac"}
ALLOWED_IMAGE_SUFFIXES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def extract_cover(tags) -> tuple[bytes, str] | None:
    if not tags:
        return None
    try:
        for picture in getattr(tags, "pictures", []) or []:
            data = getattr(picture, "data", None)
            mime = getattr(picture, "mime", "")
            if data:
                suffix = ".jpg" if "jpeg" in mime else ".png" if "png" in mime else ".webp" if "webp" in mime else ".jpg"
                return data, suffix
    except Exception:
        pass
    try:
        apic_frames = tags.tags.getall("APIC") if hasattr(tags, "tags") and tags.tags else []
        for frame in apic_frames:
            if getattr(frame, "data", None):
                mime = getattr(frame, "mime", "")
                suffix = ".jpg" if "jpeg" in mime else ".png" if "png" in mime else ".webp" if "webp" in mime else ".jpg"
                return frame.data, suffix
    except Exception:
        pass
    return None


@app.post("/api/tracks")
async def upload_track(
    file: UploadFile,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only MP3 and FLAC files are supported")
    content = await file.read(100 * 1024 * 1024 + 1)
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 100 MB")
    if suffix == ".flac" and not content.startswith(b"fLaC"):
        raise HTTPException(status_code=400, detail="Invalid FLAC file")
    if suffix == ".mp3":
        has_id3 = content.startswith(b"ID3")
        frame_sync = len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0
        if not (has_id3 or frame_sync):
            raise HTTPException(status_code=400, detail="Invalid MP3 file")
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(
        select(Track).where(Track.user_id == user.id, Track.sha256 == digest)
    )
    if existing:
        return {"id": existing.id, "duplicate": True}
    stored_name = f"{digest}{suffix}"
    try:
        stored_key = storage.upload(stored_name, content, ALLOWED_SUFFIXES[suffix])
    except Exception as error:
        code = getattr(error, "response", {}).get("Error", {}).get("Code")
        if code in {"401", "403", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
            raise HTTPException(
                status_code=502,
                detail="Object storage authentication failed",
            ) from error
        raise HTTPException(
            status_code=502,
            detail="Unable to store uploaded audio",
        ) from error
    try:
        with storage.open(stored_key) as source:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as probe:
                shutil.copyfileobj(source, probe)
                probe.flush()
                tags = MutagenFile(probe.name, easy=True)
                info = tags.info if tags else None
                duration = int(getattr(info, "length", 0) or 0)
                metadata = tags.tags if tags and tags.tags else {}
                cover = None
                raw_tags = MutagenFile(probe.name)
                if raw_tags:
                    cover = extract_cover(raw_tags)

        def first(key: str):
            value = metadata.get(key)
            return value[0] if isinstance(value, list) and value else None

        def clean_metadata(value, fallback: str = "") -> str | None:
            if value is None:
                return fallback or None
            cleaned = re.sub(r"[\x00-\x1f\x7f]", "", str(value)).strip()
            return (cleaned[:500] or fallback or None)

        title = clean_metadata(first("title"), Path(file.filename or "").stem[:500])
        artist = clean_metadata(first("artist"))
        album = clean_metadata(first("album"))
        genre = clean_metadata(first("genre"))
        year_value = first("date") or first("year")
        try:
            year = int(str(year_value)[:4]) if year_value else None
        except (TypeError, ValueError):
            year = None
    except Exception:
        storage.delete(stored_key)
        raise HTTPException(status_code=400, detail="Invalid or unreadable audio file")
    cover_path = None
    if cover:
        cover_bytes, cover_suffix = cover
        cover_path = f"covers/{digest}{cover_suffix}"
        try:
            cover_content_type = ALLOWED_IMAGE_SUFFIXES[cover_suffix]
            storage.upload(cover_path, cover_bytes, cover_content_type)
        except Exception:
            cover_path = None
    track = Track(
        user_id=user.id,
        title=str(title),
        artist=str(artist) if artist else None,
        album=str(album) if album else None,
        year=year,
        genre=str(genre) if genre else None,
        duration=duration,
        sha256=digest,
        file_name=clean_metadata(Path(file.filename or "").name, stored_name) or stored_name,
        stored_path=stored_key,
        mime_type=ALLOWED_SUFFIXES[suffix],
        cover_path=cover_path,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track_to_dict(track)


def track_to_dict(track: Track):
    return {
        "id": track.id,
        "title": str(track.title) if track.title is not None else "Canción sin título",
        "artist": str(track.artist) if track.artist is not None else None,
        "album": str(track.album) if track.album is not None else None,
        "year": track.year,
        "genre": track.genre,
        "duration": track.duration,
        "file_name": track.file_name,
        "cover_url": f"/api/tracks/{track.id}/cover" if getattr(track, "cover_path", None) else None,
    }


@app.get("/api/tracks")
def list_tracks(db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    tracks = db.scalars(select(Track).where(Track.user_id == user.id).order_by(Track.created_at.desc()))
    return [track_to_dict(track) for track in tracks]


@app.get("/api/tracks/{track_id}/cover")
def track_cover(
    track_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    track = db.scalar(select(Track).where(Track.id == track_id, Track.user_id == user.id))
    if not track or not getattr(track, "cover_path", None):
        raise HTTPException(status_code=404, detail="Cover not found")
    try:
        source = storage.open(track.cover_path)
        suffix = Path(track.cover_path).suffix.lower()
        media_type = ALLOWED_IMAGE_SUFFIXES.get(suffix, "application/octet-stream")
        return StreamingResponse(
            source,
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=86400"},
        )
    except Exception as error:
        raise HTTPException(status_code=404, detail="Cover not found") from error


@app.get("/api/search")
def search_tracks(
    q: str,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    query = q.strip()[:200]
    if not query:
        return []
    pattern = f"%{query.lower()}%"
    tracks = db.scalars(
        select(Track)
        .where(
            Track.user_id == user.id,
            (Track.title.ilike(pattern))
            | (Track.artist.ilike(pattern))
            | (Track.album.ilike(pattern))
            | (Track.genre.ilike(pattern)),
        )
        .order_by(Track.title)
        .limit(100)
    )
    return [track_to_dict(track) for track in tracks]


@app.get("/api/tracks/{track_id}/stream")
def stream_track(
    track_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
):
    track = db.scalar(select(Track).where(Track.id == track_id, Track.user_id == user.id))
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not storage.exists(track.stored_path):
        raise HTTPException(status_code=404, detail="Audio file missing")
    size = storage.size(track.stored_path)
    start, end = 0, size - 1
    status = 200
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=3600",
        "Content-Type": track.mime_type,
    }
    if range_header:
        try:
            range_unit, range_value = range_header.replace(" ", "").split("=", 1)
            if range_unit != "bytes":
                raise ValueError
            start_text, end_text = range_value.split("-", 1)
            if start_text:
                start = int(start_text)
                end = int(end_text) if end_text else size - 1
                if start < 0:
                    raise ValueError
            else:
                if not end_text:
                    raise ValueError
                suffix_length = int(end_text)
                if suffix_length <= 0:
                    raise ValueError
                start = max(0, size - suffix_length)
                end = size - 1
            if start >= size or end < start:
                raise ValueError
            end = min(end, size - 1)
            status = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        except ValueError:
            raise HTTPException(status_code=416, detail="Invalid Range")
    headers["Content-Length"] = str(end - start + 1)
    return StreamingResponse(
        iter_storage(storage, track.stored_path, start, end),
        status_code=status,
        headers=headers,
        media_type=track.mime_type,
    )


def iter_storage(provider, key: str, start: int, end: int, chunk_size: int = 256 * 1024):
    try:
        source = provider.open(key, start=start, end=end)
    except TypeError:
        source = provider.open(key)
    with source:
        remaining = end - start + 1
        while remaining:
            chunk = source.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@app.get("/api/playlists")
def list_playlists(db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    playlists = db.scalars(select(Playlist).where(Playlist.user_id == user.id).order_by(Playlist.id))
    return [{
        "id": p.id,
        "name": p.name,
        "cover_url": f"/api/playlists/{p.id}/cover" if getattr(p, "cover_path", None) else None,
    } for p in playlists]


@app.post("/api/playlists")
def create_playlist(payload: dict, db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    name = re.sub(r"[\x00-\x1f\x7f]", "", str(payload.get("name", ""))).strip()[:200]
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    playlist = Playlist(user_id=user.id, name=name)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    track_ids = payload.get("track_ids")
    if isinstance(track_ids, list):
        normalized_ids = list(dict.fromkeys(
            track_id for track_id in track_ids
            if isinstance(track_id, int)
        ))
        tracks = db.scalars(
            select(Track).where(Track.id.in_(normalized_ids), Track.user_id == user.id)
        ).all()
        for position, track in enumerate(tracks):
            db.add(PlaylistTrack(
                playlist_id=playlist.id,
                track_id=track.id,
                position=position,
            ))
        db.commit()
    return {
        "id": playlist.id,
        "name": playlist.name,
        "cover_url": None,
    }


@app.get("/api/playlists/{playlist_id}")
def get_playlist(
    playlist_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    entries = db.scalars(
        select(PlaylistTrack)
        .where(PlaylistTrack.playlist_id == playlist_id)
        .order_by(PlaylistTrack.position)
    )
    track_ids = [entry.track_id for entry in entries]
    tracks = db.scalars(select(Track).where(Track.id.in_(track_ids), Track.user_id == user.id))
    tracks_by_id = {track.id: track for track in tracks}
    return {
        "id": playlist.id,
        "name": playlist.name,
        "cover_url": f"/api/playlists/{playlist.id}/cover" if getattr(playlist, "cover_path", None) else None,
        "tracks": [track_to_dict(tracks_by_id[track_id]) for track_id in track_ids if track_id in tracks_by_id],
    }


@app.post("/api/playlists/{playlist_id}/cover")
async def update_playlist_cover(
    playlist_id: int,
    file: UploadFile,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    path, content_type = await upload_profile_image(file, f"playlist-covers/{playlist.id}")
    playlist.cover_path = path
    db.commit()
    return {"cover_url": f"/api/playlists/{playlist.id}/cover", "content_type": content_type}


@app.get("/api/playlists/{playlist_id}/cover")
def playlist_cover(
    playlist_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return image_response(getattr(playlist, "cover_path", None), "Playlist cover not found")


@app.delete("/api/playlists/{playlist_id}")
def delete_playlist(
    playlist_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    db.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == playlist_id).delete()
    db.delete(playlist)
    db.commit()
    return {"ok": True}


@app.post("/api/playlists/{playlist_id}/tracks/{track_id}")
def add_playlist_track(
    playlist_id: int,
    track_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    track = db.scalar(select(Track).where(Track.id == track_id, Track.user_id == user.id))
    if not playlist or not track:
        raise HTTPException(status_code=404, detail="Playlist or track not found")
    position = db.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == playlist_id).count()
    db.add(PlaylistTrack(playlist_id=playlist_id, track_id=track_id, position=position))
    db.commit()
    return {"ok": True}


@app.post("/api/playlists/{playlist_id}/tracks")
def add_playlist_tracks(
    playlist_id: int,
    payload: dict,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    track_ids = payload.get("track_ids")
    if not isinstance(track_ids, list):
        raise HTTPException(status_code=400, detail="track_ids must be a list")
    normalized_ids = list(dict.fromkeys(
        track_id for track_id in track_ids
        if isinstance(track_id, int)
    ))
    if not normalized_ids:
        return {"added": 0}
    tracks = db.scalars(
        select(Track).where(Track.id.in_(normalized_ids), Track.user_id == user.id)
    ).all()
    existing = set(db.scalars(
        select(PlaylistTrack.track_id).where(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.track_id.in_(normalized_ids),
        )
    ))
    position = db.query(PlaylistTrack).filter(
        PlaylistTrack.playlist_id == playlist_id
    ).count()
    added = 0
    for track in tracks:
        if track.id not in existing:
            db.add(PlaylistTrack(
                playlist_id=playlist_id,
                track_id=track.id,
                position=position,
            ))
            position += 1
            added += 1
    db.commit()
    return {"added": added}


@app.delete("/api/playlists/{playlist_id}/tracks/{track_id}")
def remove_playlist_track(
    playlist_id: int,
    track_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    entry = db.scalar(
        select(PlaylistTrack).where(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.track_id == track_id,
        )
    )
    if entry:
        db.delete(entry)
        db.commit()
    return {"ok": True}


@app.delete("/api/tracks/{track_id}")
def delete_track(
    track_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    track = db.scalar(select(Track).where(Track.id == track_id, Track.user_id == user.id))
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    storage.delete(track.stored_path)
    db.query(PlaylistTrack).filter(PlaylistTrack.track_id == track_id).delete()
    db.query(Favorite).filter(Favorite.track_id == track_id).delete()
    db.delete(track)
    db.commit()
    return {"ok": True}


@app.post("/api/favorites/{track_id}")
def add_favorite(track_id: int, db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    track = db.scalar(select(Track).where(Track.id == track_id, Track.user_id == user.id))
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    exists = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.track_id == track_id))
    if not exists:
        db.add(Favorite(user_id=user.id, track_id=track_id))
        db.commit()
    return {"ok": True}


@app.get("/api/favorites")
def list_favorites(db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    ids = db.scalars(select(Favorite.track_id).where(Favorite.user_id == user.id))
    tracks = db.scalars(select(Track).where(Track.id.in_(list(ids)), Track.user_id == user.id))
    return [track_to_dict(track) for track in tracks]


@app.delete("/api/favorites/{track_id}")
def remove_favorite(track_id: int, db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.track_id == track_id).delete()
    db.commit()
    return {"ok": True}


@app.get("/api/backup")
def create_backup(user: Annotated[User, Depends(current_user)]):
    if storage_provider_name != "local":
        raise HTTPException(status_code=400, detail="Backup is currently available only for local storage")
    backup_path = BASE_DIR / f"auralith-backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as archive:
        if DATABASE_URL.startswith("sqlite"):
            sqlite_path = DATABASE_URL.removeprefix("sqlite:///")
            if not sqlite_path.startswith("/"):
                sqlite_path = str(Path.cwd() / sqlite_path)
            archive.write(sqlite_path, "auralith.db")
        archive.write(STORAGE_DIR, "music") if False else None
        for path in STORAGE_DIR.rglob("*"):
            if path.is_file():
                archive.write(path, Path("music") / path.relative_to(STORAGE_DIR))
    return FileResponse(backup_path, media_type="application/zip", filename=backup_path.name)


@app.post("/api/restore")
async def restore_backup(
    file: UploadFile,
    user: Annotated[User, Depends(current_user)],
):
    if storage_provider_name != "local":
        raise HTTPException(status_code=400, detail="Restore is currently available only for local storage")
    if not DATABASE_URL.startswith("sqlite"):
        raise HTTPException(status_code=400, detail="Restore is currently available only for SQLite deployments")
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Backup must be a ZIP file")
    content = await file.read(1024 * 1024 * 1024)
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp:
        temp.write(content)
        temp_path = Path(temp.name)
    try:
        with zipfile.ZipFile(temp_path) as archive:
            names = set(archive.namelist())
            if "auralith.db" not in names:
                raise HTTPException(status_code=400, detail="Invalid backup: database is missing")
            total_size = sum(info.file_size for info in archive.infolist())
            if total_size > 1024 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Backup exceeds 1 GB")
            for member in archive.namelist():
                normalized = Path(member.replace("\\", "/"))
                if normalized.is_absolute() or ".." in normalized.parts:
                    raise HTTPException(status_code=400, detail="Invalid backup: unsafe path")
            sqlite_path = Path(DATABASE_URL.removeprefix("sqlite:///"))
            if not sqlite_path.is_absolute():
                sqlite_path = Path.cwd() / sqlite_path
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open("auralith.db") as source, sqlite_path.open("wb") as target:
                shutil.copyfileobj(source, target)
            shutil.rmtree(STORAGE_DIR)
            STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            for member in archive.namelist():
                if not member.startswith("music/") or member.endswith("/"):
                    continue
                relative = Path(member).relative_to("music")
                destination = STORAGE_DIR / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP backup")
    finally:
        temp_path.unlink(missing_ok=True)
    engine.dispose()
    return {"ok": True, "message": "Backup restored. Restart the API if playback does not resume."}
