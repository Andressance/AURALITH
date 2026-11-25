"""SQLAlchemy models for Auralith.

They live outside ``app.py`` so migration tooling can import the metadata without
importing the application itself (engine, storage providers, owner bootstrap,
FastAPI instance and its route table all run at import time).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    artist = Column(String)
    album = Column(String)
    year = Column(Integer)
    genre = Column(String)
    duration = Column(Integer)
    isrc = Column(String)
    sha256 = Column(String, unique=False, nullable=False, index=True)
    file_name = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    cover_path = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Playlist(Base):
    __tablename__ = "playlists"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    cover_path = Column(String)


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"
    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False)


class PlaylistShare(Base):
    __tablename__ = "playlist_shares"
    __table_args__ = (
        UniqueConstraint("playlist_id", "user_id", name="uq_playlist_share"),
    )
    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)


class Favorite(Base):
    __tablename__ = "favorites"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False, index=True)


class HiddenTrack(Base):
    __tablename__ = "hidden_tracks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False, index=True)


class Invitation(Base):
    __tablename__ = "invitations"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)
