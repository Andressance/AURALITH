"""Profile, avatar, invitation and owner user management endpoints."""

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.accounts import password_hasher
from apps.api.core.security import is_strong_owner_password
from apps.api.deps import current_user, db_session, media_user, require_owner
from apps.api.media import (
    delete_replaced_image,
    image_response,
    upload_profile_image,
    versioned_image_url,
)
from apps.api.models import (
    Favorite,
    HiddenTrack,
    Invitation,
    Playlist,
    PlaylistTrack,
    Session as UserSession,
    Track,
    User,
)
from apps.api.runtime import storage
from apps.api.serializers import user_profile

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/owner/invitations")
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

@router.post("/api/owner/invitations")
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

@router.get("/api/owner/users")
def list_users(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    require_owner(user)
    users = db.scalars(select(User).order_by(User.id)).all()
    return [
        {
            "id": account.id,
            "username": account.username,
            "display_name": getattr(account, "display_name", None) or account.username,
            "role": account.role,
            "is_owner": account.role == "owner",
        }
        for account in users
    ]

@router.delete("/api/owner/invitations/{invitation_id}")
def revoke_invitation(
    invitation_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    require_owner(user)
    invitation = db.get(Invitation, invitation_id)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    db.delete(invitation)
    db.commit()
    return {"ok": True}

@router.delete("/api/owner/users/{account_id}")
def delete_guest(
    account_id: int,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    require_owner(user)
    account = db.get(User, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="User not found")
    if account.role == "owner":
        raise HTTPException(status_code=400, detail="The owner account cannot be deleted")

    tracks = db.scalars(select(Track).where(Track.user_id == account.id)).all()
    for track in tracks:
        storage.delete(track.stored_path)
        if getattr(track, "cover_path", None):
            storage.delete(track.cover_path)

    if tracks:
        track_ids = [track.id for track in tracks]
        db.query(PlaylistTrack).filter(
            PlaylistTrack.track_id.in_(track_ids)
        ).delete(synchronize_session=False)

    guest_playlists = db.scalars(
        select(Playlist).where(Playlist.user_id == account.id)
    ).all()
    if guest_playlists:
        playlist_ids = [playlist.id for playlist in guest_playlists]
        db.query(PlaylistTrack).filter(
            PlaylistTrack.playlist_id.in_(playlist_ids)
        ).delete(synchronize_session=False)
    db.query(Favorite).filter(Favorite.user_id == account.id).delete()
    db.query(HiddenTrack).filter(HiddenTrack.user_id == account.id).delete()
    db.query(UserSession).filter(UserSession.user_id == account.id).delete()
    db.query(Playlist).filter(Playlist.user_id == account.id).delete()
    db.query(Track).filter(Track.user_id == account.id).delete()
    db.delete(account)
    db.commit()
    return {"ok": True}

@router.post("/api/invitations/{code}/activate")
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

@router.post("/api/profile")
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
    return user_profile(user)

@router.post("/api/profile/avatar")
async def update_profile_avatar(
    file: UploadFile,
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    return await update_avatar(file, db, user)

@router.get("/api/profile/avatar")
async def profile_avatar(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(media_user)],
):
    def save_path(path: str) -> None:
        user.avatar_path = path
        db.commit()

    response = await image_response(
        getattr(user, "avatar_path", None),
        "Avatar not found",
        save_path,
    )
    # Streamed image bodies must not hold a pooled database connection.
    db.close()
    return response

async def update_avatar(file: UploadFile, db: Session, user: User):
    previous_path = user.avatar_path
    path, content_type = await upload_profile_image(file, f"avatars/{user.id}")
    user.avatar_path = path
    db.commit()
    delete_replaced_image(previous_path, path)
    return {
        "avatar_url": versioned_image_url("/api/profile/avatar", Path(path).stem, user),
        "content_type": content_type,
    }
