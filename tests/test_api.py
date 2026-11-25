import os
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone

from PIL import Image

os.environ["AURALITH_OWNER_USERNAME"] = "owner"
os.environ["AURALITH_OWNER_PASSWORD"] = "TestPassword123!"
os.environ["AURALITH_ALLOW_INSECURE_COOKIES"] = "true"
os.environ["AURALITH_COOKIE_SECURE"] = "false"
os.environ["AURALITH_ALLOW_VERCEL_ORIGINS"] = "false"
os.environ["AURALITH_CORS_ORIGINS"] = "https://auralith-smoky.vercel.app"

DATA_DIR = Path(tempfile.mkdtemp(prefix="auralith-test-"))
os.environ["AURALITH_DATA_DIR"] = str(DATA_DIR)
os.environ["AURALITH_STORAGE_DIR"] = str(DATA_DIR / "music")
os.environ["AURALITH_DB_URL"] = f"sqlite:///{DATA_DIR / 'test.db'}"

# Build the test schema with the real migrations, not create_all: this way the
# baseline is exercised by the suite instead of drifting from the models.
from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
migration_config = Config(str(PROJECT_ROOT / "alembic.ini"))
migration_config.set_main_option("script_location", str(PROJECT_ROOT / "apps" / "api" / "migrations"))
command.upgrade(migration_config, "head")

from fastapi.testclient import TestClient
from apps.api.app import app
from apps.api.media import optimize_image
from apps.api.models import Playlist, Track, normalize_utc
from apps.api.runtime import SessionLocal, storage

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
        from apps.api.models import User
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
        from apps.api.models import User
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


def test_owner_can_create_activate_revoke_and_delete_guest():
    login()
    created = client.post("/api/owner/invitations", json={"display_name": "Invitado prueba"})
    assert created.status_code == 200
    invitation = created.json()

    activated = client.post(
        f"/api/invitations/{invitation['code']}/activate",
        json={
            "username": "guest1",
            "display_name": "Invitado prueba",
            "password": "GuestPassword123!",
        },
    )
    assert activated.status_code == 200
    assert activated.json()["role"] == "guest"

    users = client.get("/api/owner/users")
    assert users.status_code == 200
    guest = next(account for account in users.json() if account["username"] == "guest1")

    guest_client = TestClient(app)
    guest_login = guest_client.post(
        "/api/auth/login",
        json={"username": "guest1", "password": "GuestPassword123!"},
    )
    assert guest_login.status_code == 200

    assert guest_client.post("/api/playlists", json={"name": "Guest list"}).status_code == 200
    deleted = client.delete(f"/api/owner/users/{guest['id']}")
    assert deleted.status_code == 200


def test_guest_sees_owner_tracks_but_can_only_hide_them():
    login()
    key = "shared-track.mp3"
    storage.upload(key, b"shared-track", "audio/mpeg")
    from apps.api.models import User
    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Shared Horizon",
            sha256="shared-horizon",
            file_name="shared.mp3",
            stored_path=key,
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        track_id = track.id

    invitation = client.post("/api/owner/invitations", json={"display_name": "Shared guest"})
    code = invitation.json()["code"]
    assert client.post(
        f"/api/invitations/{code}/activate",
        json={
            "username": "sharedguest",
            "display_name": "Shared guest",
            "password": "GuestPassword123!",
        },
    ).status_code == 200

    guest_client = TestClient(app)
    assert guest_client.post(
        "/api/auth/login",
        json={"username": "sharedguest", "password": "GuestPassword123!"},
    ).status_code == 200

    tracks = guest_client.get("/api/tracks")
    assert tracks.status_code == 200
    assert any(track["id"] == track_id for track in tracks.json())
    guest_playlist = guest_client.post("/api/playlists", json={"name": "Guest shared list"})
    assert guest_client.post(
        f"/api/playlists/{guest_playlist.json()['id']}/tracks/{track_id}"
    ).status_code == 200
    assert guest_client.post(f"/api/favorites/{track_id}").status_code == 200
    assert guest_client.get(f"/api/tracks/{track_id}/stream").status_code == 200

    hidden = guest_client.delete(f"/api/tracks/{track_id}")
    assert hidden.status_code == 200
    assert hidden.json()["hidden"] is True
    assert not any(track["id"] == track_id for track in guest_client.get("/api/tracks").json())
    assert guest_client.get(f"/api/tracks/{track_id}/stream").status_code == 404
    assert guest_client.post(f"/api/favorites/{track_id}").status_code == 404
    assert guest_client.post(
        f"/api/playlists/{guest_playlist.json()['id']}/tracks/{track_id}"
    ).status_code == 404
    assert not guest_client.get("/api/favorites").json()
    assert not guest_client.get(f"/api/playlists/{guest_playlist.json()['id']}").json()["tracks"]

    owner_tracks = client.get("/api/tracks")
    assert owner_tracks.status_code == 200
    assert any(track["id"] == track_id for track in owner_tracks.json())
    assert storage.exists(key)


def test_guest_cannot_access_owner_management():
    invitation = client.post("/api/owner/invitations", json={"display_name": "Guest"})
    assert invitation.status_code == 200
    code = invitation.json()["code"]
    activated = client.post(
        f"/api/invitations/{code}/activate",
        json={
            "username": "guest2",
            "display_name": "Guest",
            "password": "GuestPassword123!",
        },
    )
    assert activated.status_code == 200

    guest_client = TestClient(app)
    guest_client.post(
        "/api/auth/login",
        json={"username": "guest2", "password": "GuestPassword123!"},
    )
    assert guest_client.get("/api/owner/users").status_code == 403
    assert guest_client.get("/api/owner/invitations").status_code == 403


def test_invalid_password_is_rejected():
    login_rate_limiter_reset()
    response = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_rate_limit_ignores_untrusted_forwarded_addresses():
    login_rate_limiter_reset()
    for attempt in range(5):
        response = client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "wrong-password"},
            headers={"X-Forwarded-For": f"198.51.100.{attempt + 1}"},
        )
        assert response.status_code == 401
    blocked = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "wrong-password"},
        headers={"X-Forwarded-For": "203.0.113.99"},
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    login_rate_limiter_reset()


def test_api_rate_limit_returns_retry_after():
    from apps.api.app import request_rate_limiter

    request_rate_limiter.attempts.clear()
    for _ in range(300):
        assert client.get("/api/health").status_code == 200
    blocked = client.get("/api/health")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    request_rate_limiter.attempts.clear()


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


def test_csv_import_matches_tracks_and_adds_only_exact_matches():
    login()
    from apps.api.models import User

    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        db.add(Track(
            user_id=owner.id,
            title="Blue Horizon",
            artist="The Tests",
            album="Release",
            duration=215,
            isrc="USABC1234567",
            sha256="csv-import-test",
            file_name="csv-import-test.mp3",
            stored_path="csv-import-test.mp3",
            mime_type="audio/mpeg",
        ))
        db.commit()
        track_id = db.query(Track).filter_by(sha256="csv-import-test").one().id

    csv_content = (
        "Title,Artist,Album,Duration,ISRC,Position\n"
        "Blue Horizon,The Tests,Release,215,USABC1234567,1\n"
        "Blue Horizon,The Tests,Release,215,USABC1234567,2\n"
        "Blue Horizonn,The Tests,Release,215,,3\n"
        "Unknown Song,Unknown Artist,,,,4\n"
    )
    response = client.post(
        "/api/playlists/import/csv",
        data={"name": "CSV import"},
        files={"file": ("tracks.csv", csv_content.encode(), "text/csv")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["added"] == 1
    assert [item["status"] for item in result["results"]] == [
        "EXACT",
        "DUPLICATE",
        "REVIEW_REQUIRED",
        "UNMATCHED",
    ]
    playlist = client.get(f"/api/playlists/{result['playlist_id']}")
    assert [track["id"] for track in playlist.json()["tracks"]] == [track_id]


def test_csv_import_rejects_invalid_encoding_and_oversized_input():
    login()
    bad_encoding = client.post(
        "/api/playlists/import/csv",
        files={"file": ("tracks.csv", b"\xff\xfe", "text/csv")},
    )
    assert bad_encoding.status_code == 400
    oversized = client.post(
        "/api/playlists/import/csv",
        files={"file": ("tracks.csv", b"x" * (2 * 1024 * 1024 + 1), "text/csv")},
    )
    assert oversized.status_code == 413


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
        from apps.api.models import User
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


def test_backup_and_restore_require_owner():
    login()
    invitation = client.post("/api/owner/invitations", json={"display_name": "Guest Backup Test"})
    code = invitation.json()["code"]
    client.post(
        f"/api/invitations/{code}/activate",
        json={
            "username": "guest_backup",
            "display_name": "Guest",
            "password": "GuestPassword123!",
        },
    )
    guest_client = TestClient(app)
    guest_client.post(
        "/api/auth/login",
        json={"username": "guest_backup", "password": "GuestPassword123!"},
    )
    backup_response = guest_client.get("/api/backup")
    assert backup_response.status_code == 403
    assert backup_response.json()["detail"] == "Owner access required"

    restore_response = guest_client.post(
        "/api/restore",
        files={"file": ("backup.zip", b"PK\x05\x06" + b"\x00" * 18, "application/zip")},
    )
    assert restore_response.status_code == 403
    assert restore_response.json()["detail"] == "Owner access required"


def test_owner_backup_contains_database_and_music():
    login()
    storage.upload("backup-test.mp3", b"backup-audio", "audio/mpeg")

    response = client.get("/api/backup")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert archive.read("music/backup-test.mp3") == b"backup-audio"
    assert "auralith.db" in names


def test_search_escapes_sql_wildcards():
    login()
    from apps.api.models import User

    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        db.add(Track(
            user_id=owner.id,
            title="Special 100% Real",
            artist="Wildcard Artist",
            sha256="wildcard-test-1",
            file_name="wildcard-test-1.mp3",
            stored_path="wildcard-test-1.mp3",
            mime_type="audio/mpeg",
        ))
        db.add(Track(
            user_id=owner.id,
            title="Special 1000 Real",
            artist="Wildcard Artist",
            sha256="wildcard-test-2",
            file_name="wildcard-test-2.mp3",
            stored_path="wildcard-test-2.mp3",
            mime_type="audio/mpeg",
        ))
        db.commit()

    percent_search = client.get("/api/search?q=100%")
    assert percent_search.status_code == 200
    titles = [t["title"] for t in percent_search.json()]
    assert "Special 100% Real" in titles
    assert "Special 1000 Real" not in titles


def login_rate_limiter_reset():
    from apps.api.core.security import login_rate_limiter
    login_rate_limiter.attempts.clear()


def test_media_urls_are_signed_and_query_tokens_are_rejected():
    login()
    key = "signed-media-test.mp3"
    storage.upload(key, b"abcdef", "audio/mpeg")
    from apps.api.models import User

    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Signed media",
            sha256="signed-media-test",
            file_name="signed-media-test.mp3",
            stored_path=key,
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        track_id = track.id

    tracks = client.get("/api/tracks").json()
    item = next(track for track in tracks if track["id"] == track_id)
    stream_url = item["stream_url"]
    assert "sig=" in stream_url
    assert "token=" not in stream_url

    anonymous = TestClient(app)
    assert anonymous.get(stream_url).status_code == 200
    assert anonymous.get(stream_url.replace("sig=", "sig=0")).status_code == 401
    assert anonymous.get(f"/api/tracks/{track_id}/stream?token=anything").status_code == 401
