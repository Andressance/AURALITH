import os
import tempfile
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone

from PIL import Image

os.environ["AURALITH_OWNER_USERNAME"] = "owner"
os.environ["AURALITH_OWNER_PASSWORD"] = "TestPassword123!"
os.environ["AURALITH_ALLOW_INSECURE_COOKIES"] = "true"
os.environ["AURALITH_COOKIE_SECURE"] = "false"

DATA_DIR = Path(tempfile.mkdtemp(prefix="auralith-test-"))
os.environ["AURALITH_DATA_DIR"] = str(DATA_DIR)
os.environ["AURALITH_STORAGE_DIR"] = str(DATA_DIR / "music")
os.environ["AURALITH_DB_URL"] = f"sqlite:///{DATA_DIR / 'test.db'}"

from fastapi.testclient import TestClient
from apps.api.app import app, Playlist, Track, SessionLocal, storage, normalize_utc, optimize_image

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


def test_bearer_session_authentication():
    response = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "TestPassword123!"},
    )
    token = response.json()["token"]
    authenticated = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert authenticated.status_code == 200
    assert authenticated.json()["username"] == "owner"


def test_owner_profile_name_is_editable():
    login()
    response = client.post(
        "/api/profile",
        json={"username": "andre", "display_name": "Andrés"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "andre"
    assert response.json()["display_name"] == "Andrés"
    assert response.json()["role"] == "owner"
    restored = client.post(
        "/api/profile",
        json={"username": "owner", "display_name": "Owner"},
    )
    assert restored.status_code == 200


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


def test_cross_origin_upload_error_has_cors_headers():
    login()
    origin = "https://auralith-smoky.vercel.app"
    response = client.post(
        "/api/tracks",
        files={"file": ("track.wav", b"RIFF", "audio/wav")},
        headers={"Origin": origin},
    )
    assert response.status_code == 400
    assert response.headers["Access-Control-Allow-Origin"] == origin
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


def test_security_headers_are_present():
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def test_image_responses_allow_private_browser_caching():
    login()
    image_buffer = BytesIO()
    Image.new("RGB", (1600, 900), color=(80, 40, 120)).save(image_buffer, format="PNG")
    image = image_buffer.getvalue()

    playlist = client.post("/api/playlists", json={"name": "Cached cover"})
    playlist_id = playlist.json()["id"]
    uploaded_cover = client.post(
        f"/api/playlists/{playlist_id}/cover",
        files={"file": ("cover.png", image, "image/png")},
    )
    assert uploaded_cover.status_code == 200
    first_cover_url = uploaded_cover.json()["cover_url"]
    assert uploaded_cover.json()["content_type"] == "image/webp"
    playlist_cover = client.get(first_cover_url)
    assert playlist_cover.headers["Cache-Control"] == "private, max-age=86400"
    assert playlist_cover.headers["content-type"] == "image/webp"
    with Image.open(BytesIO(playlist_cover.content)) as optimized_cover:
        assert optimized_cover.size == (512, 288)

    replacement = BytesIO()
    Image.new("RGB", (320, 320), color=(120, 40, 80)).save(replacement, format="PNG")
    updated_cover = client.post(
        f"/api/playlists/{playlist_id}/cover",
        files={"file": ("cover.png", replacement.getvalue(), "image/png")},
    )
    assert updated_cover.status_code == 200
    assert updated_cover.json()["cover_url"] != first_cover_url

    cover_key = "cache-test-cover.webp"
    storage.upload(cover_key, playlist_cover.content, "image/webp")
    with SessionLocal() as db:
        from apps.api.app import User
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Cached cover test",
            sha256="cached-cover-test",
            file_name="cached-cover-test.mp3",
            stored_path="cached-cover-test.mp3",
            mime_type="audio/mpeg",
            cover_path=cover_key,
        )
        db.add(track)
        db.commit()
        track_id = track.id

    track_cover = client.get(f"/api/tracks/{track_id}/cover")
    assert track_cover.headers["Cache-Control"] == "private, max-age=86400"


def test_image_optimizer_rejects_oversized_dimensions():
    oversized_ppm_header = b"P6\n5000 4000\n255\n"
    try:
        optimize_image(oversized_ppm_header)
    except ValueError as error:
        assert "dimensions" in str(error)
    else:
        raise AssertionError("Oversized artwork dimensions should be rejected")


def test_legacy_playlist_cover_is_migrated_on_first_access():
    login()
    image_buffer = BytesIO()
    Image.new("RGB", (1600, 900), color=(60, 90, 120)).save(image_buffer, format="PNG")
    legacy_path = "playlist-covers/legacy-cover.png"
    storage.upload(legacy_path, image_buffer.getvalue(), "image/png")
    playlist_id = client.post("/api/playlists", json={"name": "Legacy cover"}).json()["id"]

    with SessionLocal() as db:
        playlist = db.get(Playlist, playlist_id)
        playlist.cover_path = legacy_path
        db.commit()

    cover = client.get(f"/api/playlists/{playlist_id}/cover?v=legacy-cover")
    assert cover.status_code == 200
    assert cover.headers["content-type"] == "image/webp"
    assert cover.headers["Cache-Control"] == "private, max-age=86400"
    assert not storage.exists(legacy_path)
    with SessionLocal() as db:
        playlist = db.get(Playlist, playlist_id)
        assert playlist.cover_path.endswith(".webp")


def login_rate_limiter_reset():
    from apps.api.core.security import login_rate_limiter
    login_rate_limiter.attempts.clear()
