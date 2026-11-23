from pathlib import Path

from apps.api.infrastructure.database import SQLAlchemyDatabaseProvider
from apps.api.infrastructure.storage.local import LocalStorageProvider
from apps.api.core.security import is_strong_owner_password, LoginRateLimiter


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
