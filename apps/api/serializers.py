"""JSON shapes shared by several routes."""

import logging
from pathlib import Path

from apps.api.media import stream_url_for, versioned_image_url
from apps.api.models import Track, User

logger = logging.getLogger(__name__)

def track_to_dict(track: Track, user: User):
    return {
        "id": track.id,
        "title": str(track.title) if track.title is not None else "Canción sin título",
        "artist": str(track.artist) if track.artist is not None else None,
        "album": str(track.album) if track.album is not None else None,
        "year": track.year,
        "genre": track.genre,
        "duration": track.duration,
        "file_name": track.file_name,
        "stream_url": stream_url_for(track, user),
        "cover_url": versioned_image_url(
            f"/api/tracks/{track.id}/cover",
            track.id if getattr(track, "cover_path", None) else None,
            user,
        ),
    }

def user_profile(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": getattr(user, "display_name", None) or user.username,
        "role": user.role,
        "avatar_url": versioned_image_url(
            "/api/profile/avatar",
            Path(user.avatar_path).stem if getattr(user, "avatar_path", None) else None,
            user,
        ),
    }
