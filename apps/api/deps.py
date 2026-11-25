"""Request dependencies and per-user access guards."""

import hashlib
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.security import verify_media_signature
from apps.api.models import HiddenTrack, Session as UserSession, User, normalize_utc
from apps.api.runtime import MEDIA_SECRET, SessionLocal

def db_session():
    with SessionLocal() as db:
        yield db

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def current_user(
    db: Annotated[Session, Depends(db_session)],
    auralith_session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
):
    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization[7:].strip()
    # Session tokens are only accepted from the cookie or the Authorization header.
    # Never from a query parameter: URLs leak into logs, history and Referer headers.
    auth_token = bearer_token or auralith_session
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    digest = token_hash(auth_token)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == digest))
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

def media_user(
    db: Annotated[Session, Depends(db_session)],
    uid: Annotated[int | None, Query()] = None,
    exp: Annotated[int | None, Query()] = None,
    sig: Annotated[str | None, Query()] = None,
    auralith_session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
):
    """Authenticate media requests by signed URL, or by the normal session cookie."""
    if uid is not None or exp is not None or sig:
        if uid is None or exp is None or not sig:
            raise HTTPException(status_code=401, detail="Invalid media signature")
        if exp < int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(status_code=401, detail="Media link expired")
        if not verify_media_signature(MEDIA_SECRET, uid, exp, sig):
            raise HTTPException(status_code=401, detail="Invalid media signature")
        user = db.get(User, uid)
        if not user:
            raise HTTPException(status_code=401, detail="User no longer exists")
        return user
    return current_user(db=db, auralith_session=auralith_session, authorization=authorization)

def require_owner(user: User):
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

def is_track_hidden(db: Session, user: User, track_id: int) -> bool:
    if user.role == "owner":
        return False
    return db.scalar(
        select(HiddenTrack.id).where(
            HiddenTrack.user_id == user.id,
            HiddenTrack.track_id == track_id,
        )
    ) is not None
