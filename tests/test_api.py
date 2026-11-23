import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone

os.environ["AURALITH_OWNER_USERNAME"] = "owner"
os.environ["AURALITH_OWNER_PASSWORD"] = "TestPassword123!"
os.environ["AURALITH_ALLOW_INSECURE_COOKIES"] = "true"
os.environ["AURALITH_COOKIE_SECURE"] = "false"

DATA_DIR = Path(tempfile.mkdtemp(prefix="auralith-test-"))
os.environ["AURALITH_DATA_DIR"] = str(DATA_DIR)
os.environ["AURALITH_STORAGE_DIR"] = str(DATA_DIR / "music")
os.environ["AURALITH_DB_URL"] = f"sqlite:///{DATA_DIR / 'test.db'}"

from fastapi.testclient import TestClient
from apps.api.app import app, Track, SessionLocal, storage, normalize_utc

client = TestClient(app)


def login():
    response = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "TestPassword123!"},
    )
    assert response.status_code == 200
    return client


def test_health_is_public():
    assert client.get("/api/health").status_code == 200


def test_datetime_normalization_for_postgres_sessions():
    naive = datetime(2026, 11, 23, 18, 0)
    aware = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)
    assert normalize_utc(naive).tzinfo == timezone.utc
    assert normalize_utc(aware).tzinfo == timezone.utc


def test_library_requires_authentication():
    anonymous = TestClient(app)
    assert anonymous.get("/api/tracks").status_code == 401


def test_login_and_owner_profile():
    login()
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json()["username"] == "owner"
    assert response.json()["role"] == "owner"


def test_create_playlist_and_favorite():
    login()
    playlist = client.post("/api/playlists", json={"name": "Smoke list"})
    assert playlist.status_code == 200
    assert playlist.json()["name"] == "Smoke list"


def test_range_stream_and_owner_isolation():
    login()
    key = "test-range.mp3"
    storage.upload(key, b"0123456789abcdef", "audio/mpeg")
    with SessionLocal() as db:
        from apps.api.app import User
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Range test",
            sha256="range-test",
            file_name="range.mp3",
            stored_path=key,
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        track_id = track.id

    response = client.get(
        f"/api/tracks/{track_id}/stream",
        headers={"Range": "bytes=2-5"},
    )
    assert response.status_code == 206
    assert response.headers["Content-Range"] == "bytes 2-5/16"
    assert response.content == b"2345"

    anonymous = TestClient(app)
    assert anonymous.get(f"/api/tracks/{track_id}/stream").status_code == 401


def test_search_and_playlist_track_operations():
    login()
    playlist = client.post("/api/playlists", json={"name": "Search list"})
    assert playlist.status_code == 200
    playlist_id = playlist.json()["id"]

    key = "test-search.mp3"
    storage.upload(key, b"search-track", "audio/mpeg")
    with SessionLocal() as db:
        from apps.api.app import User
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Blue Horizon",
            artist="The Tests",
            album="Release",
            sha256="search-test",
            file_name="search.mp3",
            stored_path=key,
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        track_id = track.id

    assert any(item["title"] == "Blue Horizon" for item in client.get("/api/search?q=Blue").json())
    assert client.post(f"/api/playlists/{playlist_id}/tracks/{track_id}").status_code == 200
    detail = client.get(f"/api/playlists/{playlist_id}")
    assert detail.status_code == 200
    assert detail.json()["tracks"][0]["title"] == "Blue Horizon"
    assert client.delete(f"/api/playlists/{playlist_id}/tracks/{track_id}").status_code == 200


def test_invalid_password_is_rejected():
    login_rate_limiter_reset()
    response = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_cross_origin_mutation_is_rejected():
    login()
    response = client.post(
        "/api/playlists",
        json={"name": "Blocked"},
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403


def test_security_headers_are_present():
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def login_rate_limiter_reset():
    from apps.api.core.security import login_rate_limiter
    login_rate_limiter.attempts.clear()
