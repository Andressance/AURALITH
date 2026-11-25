from types import SimpleNamespace
from pathlib import Path

from apps.api.infrastructure.database import SQLAlchemyDatabaseProvider
from apps.api.infrastructure.storage.gdrive import GoogleDriveStorageProvider
from apps.api.infrastructure.storage.interface import StorageProvider
from apps.api.infrastructure.storage.local import LocalStorageProvider
from apps.api.infrastructure.storage.s3 import S3StorageProvider
from apps.api.infrastructure.storage.supabase import SupabaseStorageProvider
from apps.api.core.security import (
    SlidingWindowRateLimiter,
    get_client_ip,
    is_allowed_origin,
    is_strong_owner_password,
    LoginRateLimiter,
)
from apps.api.core.playlist_import import match_playlist_rows, parse_playlist_csv


def test_local_storage_round_trip(tmp_path: Path):
    storage = LocalStorageProvider(tmp_path)

    key = storage.upload("album/track.mp3", b"audio", "audio/mpeg")

    assert key == "album/track.mp3"
    assert storage.exists(key)
    assert storage.size(key) == 5
    with storage.open(key) as stream:
        assert stream.read() == b"audio"

    storage.delete(key)
    assert not storage.exists(key)


def test_local_storage_rejects_unsafe_keys(tmp_path: Path):
    storage = LocalStorageProvider(tmp_path)

    try:
        storage.upload("../outside.mp3", b"bad", "audio/mpeg")
        assert False, "unsafe key should be rejected"
    except ValueError:
        pass


def test_sqlalchemy_provider_supports_sqlite(tmp_path: Path):
    provider = SQLAlchemyDatabaseProvider(f"sqlite:///{tmp_path / 'provider.db'}")

    with provider.create_session() as session:
        assert session is not None

    assert provider.sqlite_path == tmp_path / "provider.db"
    provider.dispose()


def test_sqlalchemy_provider_normalizes_postgres_urls():
    postgres_url = "postgresql://postgres.example:password@aws-0-region.pooler.supabase.com:6543/postgres"

    normalized = SQLAlchemyDatabaseProvider.normalize_url(postgres_url)

    assert normalized.startswith("postgresql+psycopg://")
    assert ":6543/" in normalized
    assert "sslmode=require" in normalized


def test_sqlalchemy_provider_rejects_direct_supabase_host():
    direct_url = "postgresql://postgres:password@db.project.supabase.co:5432/postgres"

    try:
        SQLAlchemyDatabaseProvider.normalize_url(direct_url)
        assert False, "direct Supabase host should be rejected"
    except RuntimeError as error:
        assert "6543" in str(error)


def test_s3_provider_accepts_neon_environment(monkeypatch):
    from apps.api.infrastructure.storage.s3 import S3StorageProvider

    monkeypatch.setenv("NEON_URL", "https://storage.example.com")
    monkeypatch.setenv("NEON_STORAGE_BUCKET", "music")
    monkeypatch.setenv("NEON_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("NEON_SECRET_ACCESS_KEY", "test-secret")

    provider = S3StorageProvider()

    assert provider.endpoint == "https://storage.example.com"
    assert provider.bucket == "music"


def test_s3_provider_accepts_aws_named_neon_environment(monkeypatch):
    from apps.api.infrastructure.storage.s3 import S3StorageProvider

    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "https://storage.example.com")
    monkeypatch.setenv("AWS_BUCKET_NAME", "music")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    provider = S3StorageProvider()

    assert provider.endpoint == "https://storage.example.com"
    assert provider.bucket == "music"


def test_s3_provider_accepts_temporary_aws_credentials(monkeypatch):
    from apps.api.infrastructure.storage.s3 import S3StorageProvider

    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "https://storage.example.com")
    monkeypatch.setenv("AWS_BUCKET_NAME", "music")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "test-session")

    provider = S3StorageProvider()

    assert provider.session_token == "test-session"


def test_password_policy_rejects_weak_defaults():
    assert not is_strong_owner_password("change-me")
    assert not is_strong_owner_password("ChangeMe123456")
    assert not is_strong_owner_password("short")
    assert not is_strong_owner_password("alllowercase123")
    assert is_strong_owner_password("StrongPass123!")


def test_login_rate_limiter_blocks_after_limit():
    limiter = LoginRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("127.0.0.1")
    assert limiter.allow("127.0.0.1")
    assert not limiter.allow("127.0.0.1")
    assert limiter.allow("127.0.0.2")


def test_sliding_window_limiter_is_bounded_and_returns_retry_after():
    limiter = SlidingWindowRateLimiter(max_keys=2)
    assert limiter.check("first", limit=1, window_seconds=60) == 0
    assert limiter.check("first", limit=1, window_seconds=60) > 0
    assert limiter.check("second", limit=1, window_seconds=60) == 0
    assert limiter.check("third", limit=1, window_seconds=60) == 0
    assert len(limiter.attempts) == 2


def test_client_ip_ignores_forwarding_from_untrusted_peer(monkeypatch):
    monkeypatch.setenv("AURALITH_TRUSTED_PROXIES", "10.0.0.0/8")
    untrusted = SimpleNamespace(
        client=SimpleNamespace(host="203.0.113.8"),
        headers={"x-forwarded-for": "198.51.100.1"},
    )
    trusted = SimpleNamespace(
        client=SimpleNamespace(host="10.0.0.2"),
        headers={"x-forwarded-for": "198.51.100.1, 10.0.0.3"},
    )
    assert get_client_ip(untrusted) == "203.0.113.8"
    assert get_client_ip(trusted) == "198.51.100.1"


def test_vercel_origin_requires_explicit_opt_in(monkeypatch):
    assert not is_allowed_origin("https://example.com", set())
    monkeypatch.delenv("AURALITH_ALLOW_VERCEL_ORIGINS", raising=False)
    assert not is_allowed_origin("https://auralith.vercel.app", set())
    monkeypatch.setenv("AURALITH_ALLOW_VERCEL_ORIGINS", "true")
    assert is_allowed_origin("https://auralith.vercel.app", set())


def test_csv_parser_accepts_utf8_bom_and_semicolon_delimiters():
    rows = parse_playlist_csv(
        "\ufeffTitle;Artist;Duration;Position\nA song;An artist;3:45;1\n".encode()
    )
    assert rows[0]["title"] == "A song"
    assert rows[0]["duration"] == 225


def test_csv_parser_enforces_row_and_duration_limits():
    try:
        parse_playlist_csv(b"Title,Duration\nSong,not-a-duration\n")
        assert False, "invalid duration should be rejected"
    except ValueError as error:
        assert "duration" in str(error)

    content = "Title\n" + "".join(f"Song {index}\n" for index in range(501))
    try:
        parse_playlist_csv(content.encode())
        assert False, "more than 500 rows should be rejected"
    except ValueError as error:
        assert "500" in str(error)


def test_csv_matching_flags_version_differences_for_review():
    track = SimpleNamespace(
        id=1,
        title="Blue Horizon",
        artist="The Tests",
        album="Release",
        duration=215,
        isrc=None,
    )
    rows = parse_playlist_csv(
        b"Title,Artist,Duration\nBlue Horizon (Live),The Tests,215\n"
    )
    result = match_playlist_rows(rows, [track])[0]
    assert result["status"] == "REVIEW_REQUIRED"


def test_storage_providers_implement_protocol(tmp_path: Path):
    local = LocalStorageProvider(tmp_path)
    assert isinstance(local, StorageProvider)
    assert issubclass(LocalStorageProvider, StorageProvider)
    assert issubclass(S3StorageProvider, StorageProvider)
    assert issubclass(SupabaseStorageProvider, StorageProvider)
    assert issubclass(GoogleDriveStorageProvider, StorageProvider)


def test_s3_exists_reports_missing_objects_as_absent(monkeypatch):
    from botocore.exceptions import ClientError
    from apps.api.infrastructure.storage.s3 import S3StorageProvider

    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "https://storage.example.com")
    monkeypatch.setenv("AWS_BUCKET_NAME", "music")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")

    provider = S3StorageProvider()

    def missing(*args, **kwargs):
        raise ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )

    monkeypatch.setattr(provider.client, "head_object", missing)

    assert provider.exists("missing.mp3") is False


def test_client_ip_uses_forwarded_header_behind_render_proxy(monkeypatch):
    monkeypatch.delenv("AURALITH_TRUSTED_PROXIES", raising=False)
    request = SimpleNamespace(
        client=SimpleNamespace(host="10.28.218.22"),
        headers={"x-forwarded-for": "203.0.113.9, 10.28.218.22"},
    )
    assert get_client_ip(request) == "203.0.113.9"

