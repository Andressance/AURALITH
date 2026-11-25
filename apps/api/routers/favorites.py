"""Favorites endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import current_user, db_session, is_track_hidden
from apps.api.models import Favorite, HiddenTrack, Track, User
from apps.api.serializers import track_to_dict

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/api/favorites/{track_id}")
def add_favorite(track_id: int, db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    track = db.scalar(select(Track).where(Track.id == track_id))
    if not track or is_track_hidden(db, user, track_id):
        raise HTTPException(status_code=404, detail="Track not found")
    exists = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.track_id == track_id))
    if not exists:
        db.add(Favorite(user_id=user.id, track_id=track_id))
        db.commit()
    return {"ok": True}

@router.get("/api/favorites")
def list_favorites(db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    ids = db.scalars(select(Favorite.track_id).where(Favorite.user_id == user.id))
    hidden_ids = select(HiddenTrack.track_id).where(HiddenTrack.user_id == user.id)
    tracks = db.scalars(
        select(Track).where(
            Track.id.in_(list(ids)),
            Track.id.not_in(hidden_ids),
        )
    )
    return [track_to_dict(track, user) for track in tracks]

@router.delete("/api/favorites/{track_id}")
def remove_favorite(track_id: int, db: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(current_user)]):
    db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.track_id == track_id).delete()
    db.commit()
    return {"ok": True}
