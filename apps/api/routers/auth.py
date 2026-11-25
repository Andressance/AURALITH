"""Login, logout, password and session endpoints."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.accounts import DUMMY_PASSWORD_HASH, password_hasher
from apps.api.core.security import (
    get_client_ip,
    is_strong_owner_password,
    login_rate_limiter,
)
from apps.api.deps import current_user, db_session, token_hash
from apps.api.models import Session as UserSession, User
from apps.api.runtime import COOKIE_SAMESITE, COOKIE_SECURE
from apps.api.serializers import user_profile

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/api/auth/login")
def login(request: Request, payload: dict, db: Annotated[Session, Depends(db_session)]):
    username = str(payload.get("username", ""))[:128]
    password = str(payload.get("password", ""))[:1024]
    client_ip = get_client_ip(request)
    if not login_rate_limiter.allow(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts",
            headers={"Retry-After": str(login_rate_limiter.retry_after(client_ip))},
        )
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
    db.add(UserSession(user_id=user.id, token_hash=token_hash(token), expires_at=expires))
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

@router.post("/api/auth/logout")
def logout(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
    auralith_session: Annotated[str | None, Cookie()] = None,
):
    if auralith_session:
        db.query(UserSession).filter(UserSession.token_hash == token_hash(auralith_session)).delete()
        db.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie("auralith_session")
    return response

@router.post("/api/auth/password")
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

@router.post("/api/auth/logout-all")
def logout_all(
    db: Annotated[Session, Depends(db_session)],
    user: Annotated[User, Depends(current_user)],
):
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()
    db.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie("auralith_session")
    return response

@router.get("/api/me")
def me(user: Annotated[User, Depends(current_user)]):
    return user_profile(user)
