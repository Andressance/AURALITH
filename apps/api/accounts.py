"""Owner bootstrap and password hashing."""

import logging
import os
import re
import secrets

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.security import is_strong_owner_password
from apps.api.models import User

logger = logging.getLogger(__name__)

password_hasher = PasswordHasher()
DUMMY_PASSWORD_HASH = password_hasher.hash(secrets.token_urlsafe(32))

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
