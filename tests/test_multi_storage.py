import json

import pytest

from apps.api.infrastructure.storage.composite import MultiStorageProvider
from apps.api.infrastructure.storage.factory import build_storage_provider
from apps.api.infrastructure.storage.local import LocalStorageProvider


class FlakyProvider:
    """Local provider that can simulate an outage or a full quota."""

    def __init__(self, root, fail_reads=False, fail_writes=False):
        self.inner = LocalStorageProvider(root)
        self.fail_reads = fail_reads
        self.fail_writes = fail_writes
        self.uploaded: list[str] = []
        self.deleted: list[str] = []

    def upload(self, key, content, content_type):
        if self.fail_writes:
            raise OSError("quota exceeded")
        self.uploaded.append(key)
        return self.inner.upload(key, content, content_type)

    def open(self, key, start=None, end=None):
        if self.fail_reads:
            raise OSError("backend offline")
        return self.inner.open(key, start=start, end=end)

    def size(self, key):
        if self.fail_reads:
            raise OSError("backend offline")
        return self.inner.size(key)

    def exists(self, key):
        if self.fail_reads:
            raise OSError("backend offline")
        return self.inner.exists(key)

    def delete(self, key):
        self.deleted.append(key)
        self.inner.delete(key)


def test_mirrors_uploads_to_every_backend(tmp_path):
    first = FlakyProvider(tmp_path / "a")
    second = FlakyProvider(tmp_path / "b")
    storage = MultiStorageProvider([first, second])

    key = storage.upload("tracks/one.mp3", b"audio", "audio/mpeg")

    assert key == "tracks/one.mp3"
    assert first.uploaded == ["tracks/one.mp3"]
    assert second.uploaded == ["tracks/one.mp3"]
    assert storage.size(key) == 5
    with storage.open(key) as stream:
        assert stream.read() == b"audio"


def test_reads_fall_back_when_the_first_backend_is_down(tmp_path):
    down = FlakyProvider(tmp_path / "a", fail_reads=True)
    replica = FlakyProvider(tmp_path / "b")
    storage = MultiStorageProvider([down, replica])
    storage.upload("covers/art.webp", b"image", "image/webp")

    assert storage.size("covers/art.webp") == 5
    with storage.open("covers/art.webp", start=1, end=3) as stream:
        assert stream.read(3) == b"mag"


def test_reads_fall_back_when_the_first_backend_lacks_the_object(tmp_path):
    empty = FlakyProvider(tmp_path / "a")
    replica = FlakyProvider(tmp_path / "b")
    replica.upload("tracks/two.mp3", b"replica-copy", "audio/mpeg")
    storage = MultiStorageProvider([empty, replica])

    with storage.open("tracks/two.mp3") as stream:
        assert stream.read() == b"replica-copy"


def test_missing_everywhere_raises_file_not_found(tmp_path):
    storage = MultiStorageProvider(
        [FlakyProvider(tmp_path / "a"), FlakyProvider(tmp_path / "b")]
    )

    assert storage.exists("tracks/nope.mp3") is False
    with pytest.raises(FileNotFoundError):
        storage.open("tracks/nope.mp3")
    with pytest.raises(FileNotFoundError):
        storage.size("tracks/nope.mp3")


def test_without_mirroring_writes_only_to_the_first_healthy_backend(tmp_path):
    full = FlakyProvider(tmp_path / "a", fail_writes=True)
    healthy = FlakyProvider(tmp_path / "b")
    unused = FlakyProvider(tmp_path / "c")
    storage = MultiStorageProvider([full, healthy, unused], mirror=False)

    storage.upload("tracks/three.mp3", b"audio", "audio/mpeg")

    assert full.uploaded == []
    assert healthy.uploaded == ["tracks/three.mp3"]
    assert unused.uploaded == []


def test_upload_fails_only_when_every_backend_fails(tmp_path):
    storage = MultiStorageProvider(
        [
            FlakyProvider(tmp_path / "a", fail_writes=True),
            FlakyProvider(tmp_path / "b", fail_writes=True),
        ]
    )

    with pytest.raises(OSError):
        storage.upload("tracks/four.mp3", b"audio", "audio/mpeg")


def test_delete_reaches_every_backend(tmp_path):
    first = FlakyProvider(tmp_path / "a")
    second = FlakyProvider(tmp_path / "b")
    storage = MultiStorageProvider([first, second])
    storage.upload("tracks/five.mp3", b"audio", "audio/mpeg")

    storage.delete("tracks/five.mp3")

    assert first.deleted == ["tracks/five.mp3"]
    assert second.deleted == ["tracks/five.mp3"]
    assert not first.inner.exists("tracks/five.mp3")
    assert not second.inner.exists("tracks/five.mp3")


def test_factory_builds_replicated_providers_from_json(tmp_path, monkeypatch):
    first = tmp_path / "drive-a"
    second = tmp_path / "drive-b"
    monkeypatch.setenv(
        "AURALITH_STORAGE_PROVIDERS",
        json.dumps(
            [
                {"type": "local", "root": str(first)},
                {"type": "local", "root": str(second)},
            ]
        ),
    )

    storage = build_storage_provider(tmp_path / "default")

    assert isinstance(storage, MultiStorageProvider)
    storage.upload("tracks/six.mp3", b"audio", "audio/mpeg")
    assert (first / "tracks" / "six.mp3").read_bytes() == b"audio"
    assert (second / "tracks" / "six.mp3").read_bytes() == b"audio"


def test_factory_keeps_single_provider_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("AURALITH_STORAGE_PROVIDERS", raising=False)
    monkeypatch.setenv("AURALITH_STORAGE_PROVIDER", "local")

    storage = build_storage_provider(tmp_path)

    assert isinstance(storage, LocalStorageProvider)


def test_factory_rejects_bad_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("AURALITH_STORAGE_PROVIDERS", "[{\"type\": \"dropbox\"}]")
    with pytest.raises(RuntimeError, match="Unknown storage provider"):
        build_storage_provider(tmp_path)

    monkeypatch.setenv("AURALITH_STORAGE_PROVIDERS", "not json")
    with pytest.raises(RuntimeError, match="valid JSON"):
        build_storage_provider(tmp_path)

    monkeypatch.setenv(
        "AURALITH_STORAGE_PROVIDERS", '[{"type": "local", "bucket": "typo"}]'
    )
    with pytest.raises(RuntimeError, match="Unknown options"):
        build_storage_provider(tmp_path)
