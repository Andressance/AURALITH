import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from apps.api.infrastructure.storage.gdrive import GoogleDriveStorageProvider


class FakeDriveServer:
    """Minimal Drive v3 surface: OAuth refresh, name lookup, upload and Range reads."""

    def __init__(self):
        self.files: dict[str, dict] = {}
        self.names: list[str] = []
        self.token_calls = 0
        self.range_headers: list[str | None] = []
        self._next = 0
        self.url = ""
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                return

            def _read_body(self) -> bytes:
                length = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(length) if length else b""

            def _json(self, status: int, payload: dict) -> None:
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                parsed = urlparse(self.path)
                body = self._read_body()
                if parsed.path == "/token":
                    server.token_calls += 1
                    form = parse_qs(body.decode())
                    assert form["grant_type"] == ["refresh_token"]
                    assert form["refresh_token"] == ["test-refresh"]
                    self._json(200, {"access_token": "test-token", "expires_in": 3600})
                    return
                if parsed.path == "/upload/drive/v3/files":
                    name, content = server.parse_multipart(body)
                    self._json(200, {"id": server.create(name, content)})
                    return
                self._json(404, {"error": "not found"})

            def do_PATCH(self):
                parsed = urlparse(self.path)
                file_id = parsed.path.rsplit("/", 1)[-1]
                assert file_id in server.files
                server.files[file_id]["content"] = self._read_body()
                self._json(200, {"id": file_id})

            def do_GET(self):
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                if parsed.path == "/drive/v3/files":
                    match = re.search(r"name = '([^']*)'", query["q"][0])
                    assert match, query["q"][0]
                    name = match.group(1)
                    self._json(
                        200,
                        {
                            "files": [
                                {"id": file_id, "name": entry["name"]}
                                for file_id, entry in server.files.items()
                                if entry["name"] == name
                            ]
                        },
                    )
                    return
                if parsed.path.startswith("/drive/v3/files/"):
                    file_id = parsed.path.rsplit("/", 1)[-1]
                    entry = server.files.get(file_id)
                    if not entry:
                        self._json(404, {"error": "not found"})
                        return
                    if query.get("alt") == ["media"]:
                        self._media(entry["content"])
                        return
                    self._json(200, {"size": str(len(entry["content"]))})
                    return
                self._json(404, {"error": "not found"})

            def _media(self, content: bytes) -> None:
                range_header = self.headers.get("Range")
                server.range_headers.append(range_header)
                if range_header:
                    start, end = (
                        int(part) for part in range_header.split("=", 1)[1].split("-")
                    )
                    chunk = content[start : end + 1]
                    self.send_response(206)
                    self.send_header(
                        "Content-Range", f"bytes {start}-{end}/{len(content)}"
                    )
                else:
                    chunk = content
                    self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(chunk)))
                self.end_headers()
                self.wfile.write(chunk)

            def do_DELETE(self):
                parsed = urlparse(self.path)
                file_id = parsed.path.rsplit("/", 1)[-1]
                server.files.pop(file_id, None)
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.Handler = Handler

    def parse_multipart(self, body: bytes) -> tuple[str, bytes]:
        match = re.search(rb'\{"name".*?\}', body)
        assert match, body[:200]
        metadata = json.loads(match.group(0))
        rest = body[match.end() :]
        content = rest.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
        return metadata["name"], content

    def create(self, name: str, content: bytes) -> str:
        self._next += 1
        file_id = f"file{self._next:04d}abcdefghij"
        self.files[file_id] = {"name": name, "content": content}
        self.names.append(name)
        return file_id


@pytest.fixture
def fake_drive():
    server = FakeDriveServer()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    server.url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield server
    finally:
        httpd.shutdown()
        httpd.server_close()


def build_provider(server: FakeDriveServer) -> GoogleDriveStorageProvider:
    return GoogleDriveStorageProvider(
        client_id="client-id",
        client_secret="client-secret",
        refresh_token="test-refresh",
        folder_id="folder1234567890",
        api_base=f"{server.url}/drive/v3",
        upload_base=f"{server.url}/upload/drive/v3",
        token_url=f"{server.url}/token",
    )


def test_gdrive_round_trip_uses_range_reads(fake_drive):
    provider = build_provider(fake_drive)

    key = provider.upload("tracks/abc.mp3", b"0123456789", "audio/mpeg")

    assert key == "tracks/abc.mp3"
    assert fake_drive.names == ["tracks__abc.mp3"]
    assert provider.size(key) == 10
    assert provider.exists(key)
    with provider.open(key, start=2, end=5) as stream:
        assert stream.read() == b"2345"
    assert fake_drive.range_headers[-1] == "bytes=2-5"
    with provider.open(key) as stream:
        assert stream.read() == b"0123456789"

    provider.delete(key)

    assert not provider.exists(key)
    assert fake_drive.files == {}


def test_gdrive_upload_replaces_existing_object(fake_drive):
    provider = build_provider(fake_drive)

    provider.upload("covers/xyz.webp", b"old", "image/webp")
    provider.upload("covers/xyz.webp", b"replacement", "image/webp")

    assert len(fake_drive.files) == 1
    assert provider.size("covers/xyz.webp") == len(b"replacement")


def test_gdrive_missing_object_raises_file_not_found(fake_drive):
    provider = build_provider(fake_drive)

    assert provider.exists("tracks/missing.mp3") is False
    with pytest.raises(FileNotFoundError):
        provider.size("tracks/missing.mp3")
    with pytest.raises(FileNotFoundError):
        provider.open("tracks/missing.mp3")


def test_gdrive_refreshes_the_access_token_once(fake_drive):
    provider = build_provider(fake_drive)

    provider.upload("tracks/one.mp3", b"one", "audio/mpeg")
    provider.upload("tracks/two.mp3", b"two", "audio/mpeg")
    provider.size("tracks/one.mp3")

    assert fake_drive.token_calls == 1


def test_gdrive_requires_oauth_configuration(monkeypatch):
    for name in (
        "AURALITH_GDRIVE_CLIENT_ID",
        "AURALITH_GDRIVE_CLIENT_SECRET",
        "AURALITH_GDRIVE_REFRESH_TOKEN",
        "AURALITH_GDRIVE_FOLDER_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="AURALITH_GDRIVE_CLIENT_ID"):
        GoogleDriveStorageProvider()

    with pytest.raises(RuntimeError, match="valid Drive folder id"):
        GoogleDriveStorageProvider(
            client_id="id",
            client_secret="secret",
            refresh_token="refresh",
            folder_id="../not-a-folder",
        )
