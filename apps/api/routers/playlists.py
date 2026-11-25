"""Playlist CRUD, CSV import and playlist cover endpoints."""

import logging
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.playlist_import import (
    MAX_CSV_BYTES,
    match_playlist_rows,
    parse_playlist_csv,
)
from apps.api.deps import current_user, db_session, is_track_hidden, media_user
from apps.api.media import (
    delete_replaced_image,
    image_response,
    upload_profile_image,
    versioned_image_url,
)
from apps.api.models import HiddenTrack, Playlist, PlaylistTrack, Track, User
from apps.api.serializers import track_to_dict

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/playlists")
def list_playlists(db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    playlists = db.scalars(select(Playlist).where(Playlist.user_id == user.id).order_by(Playlist.id))
    return [{
        "id": p.id,
        "name": p.name,
        "cover_url": versioned_image_url(
            f"/api/playlists/{p.id}/cover",
            Path(p.cover_path).stem if getattr(p, "cover_path", None) else None,
            user,
        ),
    } for p in playlists]

@router.post("/api/playlists/import/csv")
async def import_playlist_csv(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
    file: UploadFile = File(...),
    name: str = Form(""),
):
    content = await file.read(MAX_CSV_BYTES + 1)
    await file.close()
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV file exceeds the 2 MB limit")
    try:
        rows = parse_playlist_csv(content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not rows:
        raise HTTPException(status_code=400, detail="CSV contains no tracks")

    hidden_ids = select(HiddenTrack.track_id).where(HiddenTrack.user_id == user.id)
    tracks = db.scalars(select(Track).where(Track.id.not_in(hidden_ids))).all()
    results = match_playlist_rows(rows, tracks)

    clean_name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:200]
    if not clean_name:
        clean_name = Path(file.filename or "").stem.strip()[:200] or "Imported playlist"
    playlist = Playlist(user_id=user.id, name=clean_name)
    db.add(playlist)
    db.flush()
    exact_track_ids = list(dict.fromkeys(
        result["track_id"]
        for result in results
        if result["status"] == "EXACT" and result["track_id"] is not None
    ))
    for position, track_id in enumerate(exact_track_ids):
        db.add(PlaylistTrack(
            playlist_id=playlist.id,
            track_id=track_id,
            position=position,
        ))
    db.commit()
    db.refresh(playlist)

    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    return {
        "playlist_id": playlist.id,
        "playlist_name": playlist.name,
        "added": len(exact_track_ids),
        "counts": counts,
        "results": results,
    }

@router.post("/api/playlists")
def create_playlist(payload: dict, db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    name = re.sub(r"[\x00-\x1f\x7f]", "", str(payload.get("name", ""))).strip()[:200]
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    tracks = []
    track_ids = payload.get("track_ids")
    if isinstance(track_ids, list):
        normalized_ids = list(dict.fromkeys(
            track_id for track_id in track_ids
            if isinstance(track_id, int) and not isinstance(track_id, bool)
        ))
        if normalized_ids:
            tracks = db.scalars(
                select(Track).where(Track.id.in_(normalized_ids))
            ).all()
            if len(tracks) != len(normalized_ids) or any(
                is_track_hidden(db, user, track.id) for track in tracks
            ):
                raise HTTPException(status_code=404, detail="One or more tracks are unavailable")
    playlist = Playlist(user_id=user.id, name=name)
    db.add(playlist)
    db.flush()
    for position, track in enumerate(tracks):
        db.add(PlaylistTrack(
            playlist_id=playlist.id,
            track_id=track.id,
            position=position,
        ))
    db.commit()
    db.refresh(playlist)
    return {
        "id": playlist.id,
        "name": playlist.name,
        "cover_url": None,
    }

@router.get("/api/playlists/{playlist_id}")
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
    cover_url = versioned_image_url(
        f"/api/playlists/{playlist.id}/cover",
        Path(playlist.cover_path).stem if getattr(playlist, "cover_path", None) else None,
        user,
    )
    if not track_ids:
        return {
            "id": playlist.id,
            "name": playlist.name,
            "cover_url": cover_url,
            "tracks": [],
        }
    hidden_ids = select(HiddenTrack.track_id).where(HiddenTrack.user_id == user.id)
    tracks = db.scalars(
        select(Track).where(
            Track.id.in_(track_ids),
            Track.id.not_in(hidden_ids),
        )
    )
    tracks_by_id = {track.id: track for track in tracks}
    return {
        "id": playlist.id,
        "name": playlist.name,
        "cover_url": cover_url,
        "tracks": [track_to_dict(tracks_by_id[track_id], user) for track_id in track_ids if track_id in tracks_by_id],
    }

@router.post("/api/playlists/{playlist_id}/cover")
async def update_playlist_cover(
    playlist_id: int,
    file: UploadFile,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    previous_path = playlist.cover_path
    path, content_type = await upload_profile_image(file, f"playlist-covers/{playlist.id}")
    playlist.cover_path = path
    db.commit()
    delete_replaced_image(previous_path, path)
    return {
        "cover_url": versioned_image_url(
            f"/api/playlists/{playlist.id}/cover",
            Path(path).stem,
            user,
        ),
        "content_type": content_type,
    }

@router.get("/api/playlists/{playlist_id}/cover")
async def playlist_cover(
    playlist_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(media_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    def save_path(path: str) -> None:
        playlist.cover_path = path
        db.commit()

    response = await image_response(
        getattr(playlist, "cover_path", None),
        "Playlist cover not found",
        save_path,
    )
    # Streamed image bodies must not hold a pooled database connection.
    db.close()
    return response

@router.delete("/api/playlists/{playlist_id}")
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

@router.post("/api/playlists/{playlist_id}/tracks/{track_id}")
def add_playlist_track(
    playlist_id: int,
    track_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    playlist = db.scalar(select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id))
    track = db.scalar(select(Track).where(Track.id == track_id))
    if not playlist or not track or is_track_hidden(db, user, track_id):
        raise HTTPException(status_code=404, detail="Playlist or track not found")
    position = db.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == playlist_id).count()
    db.add(PlaylistTrack(playlist_id=playlist_id, track_id=track_id, position=position))
    db.commit()
    return {"ok": True}

@router.post("/api/playlists/{playlist_id}/tracks")
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
        if isinstance(track_id, int) and not isinstance(track_id, bool)
    ))
    if not normalized_ids:
        return {"added": 0}
    tracks = db.scalars(
        select(Track).where(Track.id.in_(normalized_ids))
    ).all()
    if len(tracks) != len(normalized_ids) or any(
        is_track_hidden(db, user, track.id) for track in tracks
    ):
        raise HTTPException(status_code=404, detail="One or more tracks are unavailable")
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

@router.delete("/api/playlists/{playlist_id}/tracks/{track_id}")
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
