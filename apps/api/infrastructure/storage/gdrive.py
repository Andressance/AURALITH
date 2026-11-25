"""Google Drive storage adapter.

Drive addresses files by opaque id, while the rest of the application keeps
path-like keys (``covers/<digest>.webp``) and derives file suffixes from them.
The adapter therefore stores an object name derived from the key and resolves
key -> id inside the configured folder, caching the mapping per process.

Media downloads use HTTP Range, which Drive supports for binary files, so
seeking streams a slice instead of downloading the whole song.

Authentication is a user OAuth refresh token: files belong to that account and
count against its storage quota (service accounts have no quota of their own
and cannot upload to a personal Drive).
"""

import json
import logging
import os
import re
import secrets
import threading
import time
from urllib import error as urllib_error
from urllib import parse, request as urllib_request

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://www.googleapis.com/drive/v3"
DEFAULT_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
DEFAULT_TOKEN_URL = "https://oauth2.googleapis.com/token"
FOLDER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{10,200}$")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _require_https(url: str) -> None:
    parsed = parse.urlparse(url)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS:
        return
    raise RuntimeError("Google Drive endpoints must use HTTPS")


class GoogleDriveStorageProvider:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
        folder_id: str | None = None,
        api_base: str | None = None,
        upload_base: str | None = None,
        token_url: str | None = None,
    ):
        self.client_id = (client_id or os.getenv("AURALITH_GDRIVE_CLIENT_ID", "")).strip()
        self.client_secret = (
            client_secret or os.getenv("AURALITH_GDRIVE_CLIENT_SECRET", "")
        ).strip()
        self.refresh_token = (
            refresh_token or os.getenv("AURALITH_GDRIVE_REFRESH_TOKEN", "")
        ).strip()
        folder = (folder_id or os.getenv("AURALITH_GDRIVE_FOLDER_ID", "")).strip()
        missing = [
            name
            for name, value in (
                ("AURALITH_GDRIVE_CLIENT_ID", self.client_id),
                ("AURALITH_GDRIVE_CLIENT_SECRET", self.client_secret),
                ("AURALITH_GDRIVE_REFRESH_TOKEN", self.refresh_token),
                ("AURALITH_GDRIVE_FOLDER_ID", folder),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"{', '.join(missing)} required for the gdrive provider")
        if not FOLDER_ID_PATTERN.match(folder):
            raise RuntimeError("AURALITH_GDRIVE_FOLDER_ID is not a valid Drive folder id")
        self.folder_id = folder
        self.api_base = (api_base or DEFAULT_API_BASE).rstrip("/")
        self.upload_base = (upload_base or DEFAULT_UPLOAD_BASE).rstrip("/")
        self.token_url = token_url or DEFAULT_TOKEN_URL
        for endpoint in (self.api_base, self.upload_base, self.token_url):
            _require_https(endpoint)
        self._token = ""
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()
        self._ids: dict[str, str] = {}
        self._ids_lock = threading.Lock()

    # -- OAuth -----------------------------------------------------------

    def _access_token(self) -> str:
        with self._token_lock:
            now = time.time()
            if self._token and now < self._token_expires_at - 60:
                return self._token
            body = parse.urlencode(
                {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                }
            ).encode()
            request = urllib_request.Request(
                self.token_url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            try:
                with urllib_request.urlopen(request, timeout=30) as response:
                    payload = json.load(response)
            except urllib_error.HTTPError as error:
                detail = error.read().decode("utf-8", "replace")[:300]
                raise RuntimeError(
                    "Google Drive token refresh failed; check the client id, secret "
                    f"and refresh token ({error.code}: {detail})"
                ) from error
            token = payload.get("access_token")
            if not token:
                raise RuntimeError("Google Drive token endpoint returned no access_token")
            self._token = str(token)
            self._token_expires_at = now + int(payload.get("expires_in", 3600))
            return self._token

    def _open(
        self,
        url: str,
        method: str = "GET",
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 60,
    ):
        merged = dict(headers or {})
        merged["Authorization"] = f"Bearer {self._access_token()}"
        request = urllib_request.Request(url, data=data, method=method, headers=merged)
        try:
            return urllib_request.urlopen(request, timeout=timeout)
        except urllib_error.HTTPError as error:
            if error.code != 401:
                raise
        with self._token_lock:
            self._token = ""
        merged["Authorization"] = f"Bearer {self._access_token()}"
        request = urllib_request.Request(url, data=data, method=method, headers=merged)
        return urllib_request.urlopen(request, timeout=timeout)

    # -- Key resolution --------------------------------------------------

    @staticmethod
    def _object_name(key: str) -> str:
        # Drive file names cannot contain "/", and prefixes must not collide.
        name = key.strip().replace("\\", "/").replace("/", "__").replace("\x00", "")
        return name[:200] or "auralith-object"

    def _cached_id(self, key: str) -> str | None:
        with self._ids_lock:
            return self._ids.get(key)

    def _remember(self, key: str, file_id: str | None) -> None:
        with self._ids_lock:
            if file_id:
                self._ids[key] = file_id
            else:
                self._ids.pop(key, None)

    def _find_id(self, key: str, refresh: bool = False) -> str | None:
        name = self._object_name(key)
        if not refresh:
            cached = self._cached_id(key)
            if cached:
                return cached
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"name = '{escaped}' and '{self.folder_id}' in parents and trashed = false"
        )
        url = (
            f"{self.api_base}/files?q={parse.quote(query, safe='')}"
            "&fields=files(id,name)&pageSize=10&supportsAllDrives=true"
            "&includeItemsFromAllDrives=true"
        )
        with self._open(url) as response:
            payload = json.load(response)
        for item in payload.get("files", []):
            if item.get("name") == name and item.get("id"):
                self._remember(key, str(item["id"]))
                return str(item["id"])
        self._remember(key, None)
        return None

    # -- StorageProvider -------------------------------------------------

    def upload(self, key: str, content: bytes, content_type: str) -> str:
        name = self._object_name(key)
        existing = self._find_id(key)
        if existing:
            url = (
                f"{self.upload_base}/files/{parse.quote(existing)}"
                "?uploadType=media&fields=id&supportsAllDrives=true"
            )
            with self._open(
                url,
                method="PATCH",
                data=content,
                headers={"Content-Type": content_type},
                timeout=300,
            ):
                pass
            return key
        metadata = json.dumps({"name": name, "parents": [self.folder_id]}).encode()
        boundary = f"auralith-{secrets.token_hex(16)}"
        body = b"".join(
            [
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode(),
                metadata,
                f"\r\n--{boundary}\r\nContent-Type: {content_type}\r\n\r\n".encode(),
                content,
                f"\r\n--{boundary}--\r\n".encode(),
            ]
        )
        url = (
            f"{self.upload_base}/files?uploadType=multipart&fields=id"
            "&supportsAllDrives=true"
        )
        with self._open(
            url,
            method="POST",
            data=body,
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
            timeout=300,
        ) as response:
            payload = json.load(response)
        file_id = payload.get("id")
        if not file_id:
            raise RuntimeError("Google Drive upload did not return a file id")
        self._remember(key, str(file_id))
        return key

    def open(self, key: str, start: int | None = None, end: int | None = None):
        file_id = self._find_id(key)
        if not file_id:
            raise FileNotFoundError(key)
        headers: dict[str, str] = {}
        if start is not None and end is not None:
            headers["Range"] = f"bytes={start}-{end}"
        url = (
            f"{self.api_base}/files/{parse.quote(file_id)}"
            "?alt=media&supportsAllDrives=true"
        )
        try:
            return self._open(url, headers=headers, timeout=300)
        except urllib_error.HTTPError as error:
            if error.code != 404:
                raise
        self._remember(key, None)
        raise FileNotFoundError(key)

    def delete(self, key: str) -> None:
        file_id = self._find_id(key)
        self._remember(key, None)
        if not file_id:
            return
        url = f"{self.api_base}/files/{parse.quote(file_id)}?supportsAllDrives=true"
        try:
            with self._open(url, method="DELETE"):
                pass
        except urllib_error.HTTPError as error:
            if error.code != 404:
                raise

    def exists(self, key: str) -> bool:
        try:
            self.size(key)
            return True
        except FileNotFoundError:
            return False

    def size(self, key: str) -> int:
        file_id = self._find_id(key)
        if not file_id:
            raise FileNotFoundError(key)
        url = (
            f"{self.api_base}/files/{parse.quote(file_id)}"
            "?fields=size&supportsAllDrives=true"
        )
        try:
            with self._open(url) as response:
                payload = json.load(response)
        except urllib_error.HTTPError as error:
            if error.code != 404:
                raise
            self._remember(key, None)
            raise FileNotFoundError(key) from error
        return int(payload.get("size", 0))
