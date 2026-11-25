"""Upload, listing, search, playback and cover endpoints for tracks."""

import hashlib
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from mutagen import File as MutagenFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.playlist_import import normalize_isrc
from apps.api.deps import current_user, db_session, is_track_hidden, media_user
from apps.api.media import (
    ALLOWED_SUFFIXES,
    extract_cover,
    image_response,
    is_missing_storage_object,
    iter_storage,
    optimize_image_with_limit,
)
from apps.api.models import Favorite, HiddenTrack, Playlist, PlaylistTrack, Track, User
from apps.api.runtime import storage
from apps.api.serializers import track_to_dict

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/api/tracks")
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
    existing = db.scalar(select(Track).where(Track.sha256 == digest))
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
            audio_bytes = source.read()
        # Mutagen needs a named file here (BytesIO returns no easy tags), and Windows cannot
        # reopen a NamedTemporaryFile while it is still open, so write, close, then parse.
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as probe:
            probe.write(audio_bytes)
        try:
            # "is not None": a file without ID3 tags is falsy in mutagen but still has a duration.
            tags = MutagenFile(probe.name, easy=True)
            info = tags.info if tags is not None else None
            duration = int(getattr(info, "length", 0) or 0)
            metadata = tags.tags if tags is not None and tags.tags else {}
            cover = None
            raw_tags = MutagenFile(probe.name)
            if raw_tags is not None:
                cover = extract_cover(raw_tags)
        finally:
            os.unlink(probe.name)

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
        isrc_value = first("isrc") or first("tsrc")
        if not isrc_value and raw_tags and getattr(raw_tags, "tags", None):
            getall = getattr(raw_tags.tags, "getall", None)
            for frame in getall("TXXX") if callable(getall) else []:
                if str(getattr(frame, "desc", "")).casefold() == "isrc":
                    values = getattr(frame, "text", [])
                    isrc_value = values[0] if values else None
                    break
        isrc = normalize_isrc(str(isrc_value)) if isrc_value else None
    except Exception:
        logger.exception("Could not read uploaded audio %s", stored_key)
        storage.delete(stored_key)
        raise HTTPException(status_code=400, detail="Invalid or unreadable audio file")
    cover_path = None
    if cover:
        try:
            cover_bytes = await optimize_image_with_limit(cover[0])
            cover_path = f"covers/{digest}.webp"
            storage.upload(cover_path, cover_bytes, "image/webp")
        except ValueError as error:
            logger.warning("Skipping invalid or oversized embedded artwork: %s", error)
            cover_path = None
        except Exception:
            logger.exception("Unable to store embedded artwork for track %s", digest)
            cover_path = None
    track = Track(
        user_id=user.id,
        title=str(title),
        artist=str(artist) if artist else None,
        album=str(album) if album else None,
        year=year,
        genre=str(genre) if genre else None,
        duration=duration,
        isrc=isrc,
        sha256=digest,
        file_name=clean_metadata(Path(file.filename or "").name, stored_name) or stored_name,
        stored_path=stored_key,
        mime_type=ALLOWED_SUFFIXES[suffix],
        cover_path=cover_path,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track_to_dict(track, user)

@router.get("/api/tracks")
def list_tracks(db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    hidden_ids = db.scalars(
        select(HiddenTrack.track_id).where(HiddenTrack.user_id == user.id)
    ).all()
    statement = select(Track)
    if hidden_ids:
        statement = statement.where(Track.id.not_in(hidden_ids))
    tracks = db.scalars(statement.order_by(Track.created_at.desc()))
    return [track_to_dict(track, user) for track in tracks]

@router.get("/api/tracks/{track_id}/cover")
async def track_cover(
    track_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(media_user)],
):
    track = db.scalar(select(Track).where(Track.id == track_id))
    if not track or is_track_hidden(db, user, track_id) or not getattr(track, "cover_path", None):
        raise HTTPException(status_code=404, detail="Cover not found")

    def save_path(path: str) -> None:
        track.cover_path = path
        db.commit()

    response = await image_response(track.cover_path, "Cover not found", save_path)
    # Streamed image bodies must not hold a pooled database connection.
    db.close()
    return response

def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

@router.get("/api/search")
def search_tracks(
    q: str,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    query = q.strip()[:200]
    if not query:
        return []
    escaped = escape_like(query.lower())
    pattern = f"%{escaped}%"
    hidden_ids = db.scalars(
        select(HiddenTrack.track_id).where(HiddenTrack.user_id == user.id)
    ).all()
    statement = select(Track).where(
        (Track.title.ilike(pattern, escape="\\"))
        | (Track.artist.ilike(pattern, escape="\\"))
        | (Track.album.ilike(pattern, escape="\\"))
        | (Track.genre.ilike(pattern, escape="\\"))
    )
    if hidden_ids:
        statement = statement.where(Track.id.not_in(hidden_ids))
    tracks = db.scalars(statement.order_by(Track.title).limit(100))
    return [track_to_dict(track, user) for track in tracks]

@router.get("/api/tracks/{track_id}/stream")
def stream_track(
    track_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(media_user)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
):
    track = db.scalar(select(Track).where(Track.id == track_id))
    if not track or is_track_hidden(db, user, track_id):
        raise HTTPException(status_code=404, detail="Track not found")
    stored_path = track.stored_path
    mime_type = track.mime_type
    # Return the pooled connection before streaming: the response body can last
    # for minutes and must not keep a database connection checked out.
    db.close()
    try:
        size = storage.size(stored_path)
    except Exception as error:
        if is_missing_storage_object(error):
            raise HTTPException(status_code=404, detail="Audio file missing") from error
        logger.warning("Unable to read audio object %s: %s", stored_path, error)
        raise HTTPException(status_code=503, detail="Audio temporarily unavailable") from error
    start, end = 0, size - 1
    status = 200
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=3600",
        "Content-Type": mime_type,
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
        iter_storage(storage, stored_path, start, end),
        status_code=status,
        headers=headers,
        media_type=mime_type,
    )

@router.delete("/api/tracks/{track_id}")
def delete_track(
    track_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    track = db.scalar(select(Track).where(Track.id == track_id))
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if user.role != "owner":
        hidden = db.scalar(
            select(HiddenTrack).where(
                HiddenTrack.user_id == user.id,
                HiddenTrack.track_id == track_id,
            )
        )
        if not hidden:
            db.add(HiddenTrack(user_id=user.id, track_id=track_id))
            db.query(Favorite).filter(
                Favorite.user_id == user.id,
                Favorite.track_id == track_id,
            ).delete()
            guest_playlist_ids = db.scalars(
                select(Playlist.id).where(Playlist.user_id == user.id)
            ).all()
            if guest_playlist_ids:
                db.query(PlaylistTrack).filter(
                    PlaylistTrack.playlist_id.in_(guest_playlist_ids),
                    PlaylistTrack.track_id == track_id,
                ).delete(synchronize_session=False)
            db.commit()
        return {"ok": True, "hidden": True}
    storage.delete(track.stored_path)
    db.query(PlaylistTrack).filter(PlaylistTrack.track_id == track_id).delete()
    db.query(Favorite).filter(Favorite.track_id == track_id).delete()
    db.delete(track)
    db.commit()
    return {"ok": True}
