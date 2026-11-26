import os
import sqlite3
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
        database_bytes = archive.read("auralith.db")
    assert "auralith.db" in names
    # The snapshot must be a readable SQLite database, not a half-written file copy.
    with sqlite3.connect(":memory:") as restored:
        restored.deserialize(database_bytes)
        tables = {row[0] for row in restored.execute("select name from sqlite_master where type='table'")}
    assert {"users", "tracks", "playlists"} <= tables


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


def test_jams_are_shared_and_anyone_can_control():
    login()
    owner_token = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "TestPassword123!"},
    ).json()["token"]

    invitation = client.post("/api/owner/invitations", json={"display_name": "Jammer"})
    code = invitation.json()["code"]
    assert client.post(
        f"/api/invitations/{code}/activate",
        json={
            "username": "jammer",
            "display_name": "Jammer",
            "password": "GuestPassword123!",
        },
    ).status_code == 200
    guest_client = TestClient(app)
    assert guest_client.post(
        "/api/auth/login",
        json={"username": "jammer", "password": "GuestPassword123!"},
    ).status_code == 200

    created = client.post("/api/jams").json()
    jam_code = created["code"]
    assert len(jam_code) == 6
    assert created["state"]["participants"][0]["username"] == "owner"

    # A jam is not readable until you join it.
    assert guest_client.get(f"/api/jams/{jam_code}").status_code == 403
    joined = guest_client.post("/api/jams/join", json={"code": jam_code})
    assert joined.status_code == 200
    assert {p["username"] for p in joined.json()["state"]["participants"]} == {
        "owner",
        "jammer",
    }

    storage.upload("jam-track.mp3", b"jam-audio", "audio/mpeg")
    from apps.api.models import User

    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Jam tune",
            sha256="jam-tune",
            file_name="jam.mp3",
            stored_path="jam-track.mp3",
            duration=180,
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        track_id = track.id

    assert guest_client.post(
        f"/api/jams/{jam_code}/queue", json={"track_id": track_id}
    ).status_code == 200

    # Everyone in the jam can drive playback, not only the host.
    assert guest_client.post(
        f"/api/jams/{jam_code}/control", json={"action": "play", "track_id": track_id}
    ).status_code == 200
    state = client.get(f"/api/jams/{jam_code}").json()
    assert state["current_track"]["id"] == track_id
    assert state["is_playing"] is True

    # next takes the first queued track and clears it.
    assert guest_client.post(
        f"/api/jams/{jam_code}/control", json={"action": "next"}
    ).status_code == 200
    state = client.get(f"/api/jams/{jam_code}").json()
    assert state["current_track"]["id"] == track_id
    assert state["queue"] == []

    # The socket sends a snapshot to a member and refuses a bad token.
    with client.websocket_connect(f"/ws/jam/{jam_code}") as socket:
        socket.send_json({"token": owner_token})
        message = socket.receive_json()
        assert message["type"] == "state"
        assert message["state"]["code"] == jam_code

    outsider = TestClient(app)
    rejected = False
    try:
        with outsider.websocket_connect(f"/ws/jam/{jam_code}") as socket:
            socket.send_json({"token": "not-a-real-token"})
            socket.receive_json()
    except Exception:
        rejected = True
    assert rejected

    assert client.post(f"/api/jams/{jam_code}/end").status_code == 200
    assert client.get(f"/api/jams/{jam_code}").status_code == 404


def _owner_track(title: str, key: str) -> int:
    from apps.api.models import User

    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title=title,
            sha256=key,
            file_name=f"{key}.mp3",
            stored_path=f"{key}.mp3",
            duration=120,
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        return track.id


def test_jam_queue_order_next_guard_and_device_relay():
    login()
    owner_token = client.post(
        "/api/auth/login", json={"username": "owner", "password": "TestPassword123!"}
    ).json()["token"]
    jam_code = client.post("/api/jams").json()["code"]
    first = _owner_track("Queue first", "queue-first")
    second = _owner_track("Queue second", "queue-second")

    client.post(f"/api/jams/{jam_code}/queue", json={"track_id": first})
    client.post(f"/api/jams/{jam_code}/queue", json={"track_id": second, "front": True})
    queue = [item["track"]["id"] for item in client.get(f"/api/jams/{jam_code}").json()["queue"]]
    assert queue == [second, first]

    queue_item_ids = [item["id"] for item in client.get(f"/api/jams/{jam_code}").json()["queue"]]
    assert client.post(
        f"/api/jams/{jam_code}/queue/{queue_item_ids[1]}/move", json={"direction": "up"}
    ).status_code == 200
    queue = [item["track"]["id"] for item in client.get(f"/api/jams/{jam_code}").json()["queue"]]
    assert queue == [first, second]
    assert client.post(
        f"/api/jams/{jam_code}/queue/{queue_item_ids[1]}/move", json={"direction": "sideways"}
    ).status_code == 400

    # A late "ended" from a client that heard another track must not skip the current one.
    client.post(f"/api/jams/{jam_code}/control", json={"action": "play", "track_id": second})
    client.post(f"/api/jams/{jam_code}/control", json={"action": "next", "expected_track_id": first})
    state = client.get(f"/api/jams/{jam_code}").json()
    assert state["current_track"]["id"] == second
    assert len(state["queue"]) == 2

    client.post(f"/api/jams/{jam_code}/control", json={"action": "next", "expected_track_id": second})
    state = client.get(f"/api/jams/{jam_code}").json()
    assert state["current_track"]["id"] == first
    assert [item["track"]["id"] for item in state["queue"]] == [second]

    # With nothing queued, next stops instead of replaying the same track.
    client.post(f"/api/jams/{jam_code}/control", json={"action": "next"})
    client.post(f"/api/jams/{jam_code}/control", json={"action": "next"})
    state = client.get(f"/api/jams/{jam_code}").json()
    assert state["queue"] == []
    assert state["is_playing"] is False
    client.post(f"/api/jams/{jam_code}/end")

    with client.websocket_connect("/ws/devices") as laptop:
        laptop.send_json({"token": owner_token, "device_id": "laptop", "name": "Laptop"})
        assert laptop.receive_json()["devices"][0]["device_id"] == "laptop"
        with client.websocket_connect("/ws/devices") as phone:
            phone.send_json({"token": owner_token, "device_id": "phone", "name": "Phone"})
            assert {d["device_id"] for d in phone.receive_json()["devices"]} == {"laptop", "phone"}
            laptop.receive_json()
            laptop.send_json(
                {"type": "presence", "is_playing": True, "position": 12, "track": {"id": 7, "title": "Hi", "stream_url": "x"}}
            )
            listed = {d["device_id"]: d for d in phone.receive_json()["devices"]}
            assert listed["laptop"]["is_playing"] is True
            assert listed["laptop"]["track"] == {"id": 7, "title": "Hi", "artist": "", "cover_url": None}
            laptop.receive_json()
            phone.send_json({"type": "relay", "target": "laptop", "message": {"cmd": "next"}})
            assert laptop.receive_json() == {"type": "relay", "from": "phone", "message": {"cmd": "next"}}

    outsider = TestClient(app)
    with outsider.websocket_connect("/ws/devices") as socket:
        socket.send_json({"token": "not-a-real-token", "device_id": "x"})
        try:
            socket.receive_json()
            raise AssertionError("bad token must not be accepted")
        except AssertionError:
            raise
        except Exception:
            pass


def _receive_until(socket, predicate):
    for _ in range(10):
        message = socket.receive_json()
        if predicate(message):
            return message
    raise AssertionError("expected message never arrived")


def test_only_one_device_per_profile_plays_at_a_time():
    login()
    owner_token = client.post(
        "/api/auth/login", json={"username": "owner", "password": "TestPassword123!"}
    ).json()["token"]
    with client.websocket_connect("/ws/devices") as tab_a:
        tab_a.send_json({"token": owner_token, "device_id": "tab-a", "name": "A"})
        _receive_until(tab_a, lambda m: m["type"] == "devices")
        with client.websocket_connect("/ws/devices") as tab_b:
            tab_b.send_json({"token": owner_token, "device_id": "tab-b", "name": "B"})
            _receive_until(tab_b, lambda m: m["type"] == "devices")
            _receive_until(tab_a, lambda m: m["type"] == "devices")

            tab_a.send_json({"type": "presence", "is_playing": True, "position": 1, "track": None})
            _receive_until(tab_a, lambda m: m["type"] == "devices")
            _receive_until(tab_b, lambda m: m["type"] == "devices")

            # Starting playback on B pauses A and the list says only B is playing.
            tab_b.send_json({"type": "presence", "is_playing": True, "position": 2, "track": None})
            pause = _receive_until(tab_a, lambda m: m["type"] == "relay")
            assert pause["message"] == {"cmd": "pause"}
            listed = {d["device_id"]: d["is_playing"] for d in _receive_until(tab_b, lambda m: m["type"] == "devices")["devices"]}
            assert listed == {"tab-a": False, "tab-b": True}


def test_playlist_collaboration_and_library_saving():
    login()
    invitation = client.post("/api/owner/invitations", json={"display_name": "Collab"})
    code = invitation.json()["code"]
    assert client.post(
        f"/api/invitations/{code}/activate",
        json={
            "username": "collab",
            "display_name": "Collab",
            "password": "GuestPassword123!",
        },
    ).status_code == 200
    guest_client = TestClient(app)
    assert guest_client.post(
        "/api/auth/login",
        json={"username": "collab", "password": "GuestPassword123!"},
    ).status_code == 200

    playlist = client.post("/api/playlists", json={"name": "Collab mix"}).json()
    storage.upload("collab-track.mp3", b"collab-audio", "audio/mpeg")
    from apps.api.models import User

    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Collab tune",
            sha256="collab-tune",
            file_name="collab.mp3",
            stored_path="collab-track.mp3",
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        track_id = track.id

    assert client.post(
        f"/api/playlists/{playlist['id']}/shares", json={"username": "collab"}
    ).status_code == 200

    # A viewer cannot change the playlist.
    assert guest_client.post(
        f"/api/playlists/{playlist['id']}/tracks/{track_id}"
    ).status_code == 404

    share = client.get(f"/api/playlists/{playlist['id']}/shares").json()[0]
    assert share["role"] == "viewer"
    promoted = client.patch(
        f"/api/playlists/{playlist['id']}/shares/{share['user_id']}",
        json={"role": "editor"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "editor"

    detail = guest_client.get(f"/api/playlists/{playlist['id']}").json()
    assert detail["role"] == "editor"
    assert guest_client.post(
        f"/api/playlists/{playlist['id']}/tracks/{track_id}"
    ).status_code == 200
    assert len(
        guest_client.get(f"/api/playlists/{playlist['id']}").json()["tracks"]
    ) == 1

    # Collaborators still cannot delete the playlist or hand out access.
    assert guest_client.delete(f"/api/playlists/{playlist['id']}").status_code == 404
    assert guest_client.post(
        f"/api/playlists/{playlist['id']}/shares", json={"username": "owner"}
    ).status_code == 404

    # A shared playlist can be removed from the library and added back.
    assert guest_client.delete(
        f"/api/playlists/{playlist['id']}/library"
    ).status_code == 200
    listing = guest_client.get("/api/playlists").json()
    assert next(item for item in listing if item["id"] == playlist["id"])["saved"] is False
    assert guest_client.post(
        f"/api/playlists/{playlist['id']}/library"
    ).status_code == 200
    listing = guest_client.get("/api/playlists").json()
    assert next(item for item in listing if item["id"] == playlist["id"])["saved"] is True


def test_playlist_sharing_is_explicit_and_revocable():
    login()
    invitation = client.post("/api/owner/invitations", json={"display_name": "Sharee"})
    code = invitation.json()["code"]
    assert client.post(
        f"/api/invitations/{code}/activate",
        json={
            "username": "sharee",
            "display_name": "Sharee",
            "password": "GuestPassword123!",
        },
    ).status_code == 200
    guest_client = TestClient(app)
    assert guest_client.post(
        "/api/auth/login",
        json={"username": "sharee", "password": "GuestPassword123!"},
    ).status_code == 200

    playlist = client.post("/api/playlists", json={"name": "Shared mix"}).json()

    # Nothing is visible until it is shared explicitly.
    assert guest_client.get(f"/api/playlists/{playlist['id']}").status_code == 404
    assert guest_client.get(f"/api/playlists/{playlist['id']}/cover").status_code == 404

    assert client.post(
        f"/api/playlists/{playlist['id']}/shares", json={"username": "nobody"}
    ).status_code == 404
    assert client.post(
        f"/api/playlists/{playlist['id']}/shares", json={"username": "owner"}
    ).status_code == 400

    shared = client.post(
        f"/api/playlists/{playlist['id']}/shares", json={"username": "sharee"}
    )
    assert shared.status_code == 200

    detail = guest_client.get(f"/api/playlists/{playlist['id']}")
    assert detail.status_code == 200
    assert detail.json()["shared"] is True
    assert detail.json()["owner"]
    assert any(
        item["id"] == playlist["id"] and item["shared"] is True
        for item in guest_client.get("/api/playlists").json()
    )

    # A shared playlist is read-only and its shares belong to the owner.
    assert guest_client.get(f"/api/playlists/{playlist['id']}/shares").status_code == 404
    assert guest_client.post(
        f"/api/playlists/{playlist['id']}/shares", json={"username": "owner"}
    ).status_code == 404
    assert guest_client.delete(f"/api/playlists/{playlist['id']}").status_code == 404

    shares = client.get(f"/api/playlists/{playlist['id']}/shares")
    assert shares.status_code == 200
    assert [item["username"] for item in shares.json()] == ["sharee"]

    assert client.delete(
        f"/api/playlists/{playlist['id']}/shares/{shared.json()['user_id']}"
    ).status_code == 200
    assert guest_client.get(f"/api/playlists/{playlist['id']}").status_code == 404
    assert all(
        item["id"] != playlist["id"]
        for item in guest_client.get("/api/playlists").json()
    )


def test_listening_stats_and_yearly_wrapped():
    login()
    from apps.api.models import User

    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Wrapped Song",
            artist="Wrapped Artist",
            album="Wrapped Album",
            duration=200,
            sha256="wrapped-stats-test",
            file_name="wrapped-stats-test.mp3",
            stored_path="wrapped-stats-test.mp3",
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        track_id = track.id

    assert client.post(
        "/api/stats/plays", json={"track_id": track_id, "seconds": 180}
    ).status_code == 200
    assert client.post(
        "/api/stats/plays", json={"track_id": track_id, "seconds": 20}
    ).status_code == 200

    year = datetime.now(timezone.utc).year
    years = client.get("/api/stats/years")
    assert years.status_code == 200
    assert year in years.json()

    wrapped = client.get(f"/api/stats/wrapped?year={year}")
    assert wrapped.status_code == 200
    body = wrapped.json()
    assert body["year"] == year
    assert body["total_seconds"] >= 200
    assert body["total_plays"] >= 2
    assert any(
        item["id"] == track_id and item["plays"] >= 2 for item in body["top_tracks"]
    )
    assert any(
        artist["name"] == "Wrapped Artist" and artist["seconds"] >= 200
        for artist in body["top_artists"]
    )
    assert any(album["name"] == "Wrapped Album" for album in body["top_albums"])
    assert len(body["monthly"]) == 12
    assert body["monthly"][datetime.now(timezone.utc).month - 1]["seconds"] >= 200
    assert body["busiest_day"] and body["busiest_day"]["seconds"] >= 200

    # A zero-second report is ignored, an unknown track is not recorded, and stats
    # belong to the signed-in account.
    assert client.post(
        "/api/stats/plays", json={"track_id": track_id, "seconds": 0}
    ).json()["recorded"] is False
    assert client.post(
        "/api/stats/plays", json={"track_id": 999999, "seconds": 10}
    ).status_code == 404
    anonymous = TestClient(app)
    assert anonymous.get("/api/stats/wrapped").status_code == 401
    assert anonymous.post(
        "/api/stats/plays", json={"track_id": track_id, "seconds": 5}
    ).status_code == 401


def test_stats_overview_breakdowns_and_dashboard_layout():
    login()
    from apps.api.models import User

    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Dashboard Song",
            artist="Dashboard Artist",
            album="Dashboard Album",
            genre="Grunge",
            duration=260,
            sha256="dashboard-stats-test",
            file_name="dashboard-stats-test.mp3",
            stored_path="dashboard-stats-test.mp3",
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        track_id = track.id

    assert client.post(
        "/api/stats/plays", json={"track_id": track_id, "seconds": 240}
    ).status_code == 200

    overview = client.get("/api/stats/overview?period=all")
    assert overview.status_code == 200
    body = overview.json()
    assert body["period"] == "all"
    assert body["totals"]["seconds"] >= 240
    assert body["totals"]["unique_tracks"] >= 1
    assert len(body["hourly"]) == 24
    assert len(body["weekday"]) == 7
    assert len(body["monthly"]) == 12
    assert sum(item["seconds"] for item in body["hourly"]) >= 240
    assert sum(item["seconds"] for item in body["weekday"]) >= 240
    assert max(item["seconds"] for item in body["hourly"]) >= 240
    assert any(
        artist["name"] == "Dashboard Artist" for artist in body["top_artists"]
    )
    assert any(genre["name"] == "Grunge" for genre in body["top_genres"])
    assert any(album["name"] == "Dashboard Album" for album in body["top_albums"])

    # The layout belongs to the account: defaults, saved edits and a reset.
    default = client.get("/api/stats/dashboard")
    assert default.status_code == 200
    assert len(default.json()["widgets"]) >= 6
    custom = [
        {
            "id": "hours",
            "title": "Mis horas",
            "type": "columns",
            "dimension": "hours",
            "metric": "plays",
        },
        {
            "id": "genres",
            "title": "Géneros",
            "type": "donut",
            "dimension": "genres",
            "metric": "minutes",
        },
    ]
    saved = client.put("/api/stats/dashboard", json={"widgets": custom})
    assert saved.status_code == 200
    assert [widget["id"] for widget in saved.json()["widgets"]] == ["hours", "genres"]
    assert len(client.put("/api/stats/dashboard", json={"widgets": custom}).json()["widgets"]) == 2
    assert client.get("/api/stats/dashboard").json()["widgets"][0]["title"] == "Mis horas"

    invalid = client.put(
        "/api/stats/dashboard",
        json={
            "widgets": [
                {"id": "x", "type": "bars", "dimension": "bogus", "metric": "minutes"}
            ]
        },
    )
    assert invalid.status_code == 400
    too_many = client.put(
        "/api/stats/dashboard",
        json={
            "widgets": [
                {"id": f"w{index}", "type": "bars", "dimension": "artists", "metric": "minutes"}
                for index in range(13)
            ]
        },
    )
    assert too_many.status_code == 400
    untitled = client.put(
        "/api/stats/dashboard",
        json={
            "widgets": [
                {"id": "blank", "title": " ", "type": "donut", "dimension": "genres", "metric": "minutes"}
            ]
        },
    )
    assert untitled.status_code == 200
    assert untitled.json()["widgets"][0]["title"] == "Géneros más escuchados"

    # Years without plays use the date range and return an empty summary.
    empty_year = client.get("/api/stats/wrapped?year=1990")
    assert empty_year.status_code == 200
    assert empty_year.json()["total_seconds"] == 0
    assert empty_year.json()["top_artists"] == []
    monthly = client.get("/api/stats/overview?period=month")
    assert monthly.status_code == 200
    assert len(monthly.json()["monthly"]) == 12
    assert monthly.json()["label"].endswith(str(datetime.now(timezone.utc).year))

    reset = client.post("/api/stats/dashboard/reset")
    assert reset.status_code == 200
    assert len(reset.json()["widgets"]) >= 6
    assert client.get("/api/stats/overview?period=week").status_code == 422
    anonymous = TestClient(app)
    assert anonymous.get("/api/stats/dashboard").status_code == 401
    assert anonymous.get("/api/stats/overview").status_code == 401


def test_listening_history_export_and_retention():
    login()
    from apps.api.models import ListeningPlay, User

    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        track = Track(
            user_id=owner.id,
            title="Historial con acentos",
            artist="Artista Ñandú",
            album="Álbum de prueba",
            genre="Folk",
            duration=210,
            sha256="history-export-test",
            file_name="history-export-test.mp3",
            stored_path="history-export-test.mp3",
            mime_type="audio/mpeg",
        )
        db.add(track)
        db.commit()
        track_id = track.id

    for seconds in (120, 60):
        assert client.post(
            "/api/stats/plays", json={"track_id": track_id, "seconds": seconds}
        ).status_code == 200

    # Retention needs an old session; the API only ever writes the current date.
    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "owner").first()
        db.add(
            ListeningPlay(
                user_id=owner.id,
                track_id=track_id,
                seconds=45,
                played_at=datetime(2020, 5, 1, 12, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()

    exported = client.get("/api/stats/plays/export")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    assert 'filename="auralith-historico.csv"' in exported.headers["content-disposition"]
    assert exported.headers["cache-control"] == "no-store"
    lines = [line for line in exported.text.lstrip("\ufeff").splitlines() if line]
    assert lines[0] == "fecha,titulo,artista,album,genero,segundos"
    assert any(
        "Historial con acentos" in line and "Artista Ñandú" in line and ",120" in line
        for line in lines[1:]
    )
    # Oldest first, so a spreadsheet reads chronologically.
    assert lines[1].startswith("2020-05-01")

    # Ambiguous or nonsensical retention requests are rejected before touching rows.
    assert client.delete("/api/stats/plays").status_code == 400
    assert client.delete(
        "/api/stats/plays", params={"days": 30, "everything": "true"}
    ).status_code == 400
    assert client.delete("/api/stats/plays", params={"days": 0}).status_code == 422

    trimmed = client.delete("/api/stats/plays", params={"days": 30})
    assert trimmed.status_code == 200
    assert trimmed.json()["deleted"] == 1
    assert "2020-05-01" not in client.get("/api/stats/plays/export").text

    wiped = client.delete("/api/stats/plays", params={"everything": "true"})
    assert wiped.status_code == 200
    assert wiped.json()["deleted"] >= 2
    remaining = client.get("/api/stats/plays/export").text.lstrip("\ufeff").splitlines()
    assert [line for line in remaining if line] == [
        "fecha,titulo,artista,album,genero,segundos"
    ]

    anonymous = TestClient(app)
    assert anonymous.get("/api/stats/plays/export").status_code == 401
    assert anonymous.delete(
        "/api/stats/plays", params={"everything": "true"}
    ).status_code == 401
