import os
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib import request as urllib_request
from urllib.parse import urlparse


class SupabaseStorageProvider:
    """Supabase Storage adapter using the REST API."""

    def __init__(
        self,
        url: str | None = None,
        service_key: str | None = None,
        bucket: str = "music",
    ):
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.service_key = (
            service_key
            or os.getenv("SUPABASE_SECRET_KEY", "")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        )
        self.bucket = bucket
        if not self.url or not self.service_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise RuntimeError("SUPABASE_URL must use HTTPS")
        if parsed.username or parsed.password or parsed.port:
            raise RuntimeError("SUPABASE_URL must not include credentials or a custom port")

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _open(request: Request, timeout: int = 30):
        class RejectRedirect(urllib_request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib_request.build_opener(RejectRedirect())
        return opener.open(request, timeout=timeout)

    def upload(self, key: str, content: bytes, content_type: str) -> str:
        endpoint = f"{self.url}/storage/v1/object/{quote(self.bucket)}/{quote(key, safe='/')}"
        request = Request(
            endpoint,
            data=content,
            method="POST",
            headers=self._headers({"Content-Type": content_type, "x-upsert": "true"}),
        )
        with self._open(request):
            pass
        return key

    def open(self, key: str):
        endpoint = f"{self.url}/storage/v1/object/authenticated/{quote(self.bucket)}/{quote(key, safe='/')}"
        return self._open(Request(endpoint, headers=self._headers()))

    def delete(self, key: str) -> None:
        endpoint = f"{self.url}/storage/v1/object/{quote(self.bucket)}"
        request = Request(
            endpoint,
            data=f'["{key}"]'.encode(),
            method="DELETE",
            headers=self._headers({"Content-Type": "application/json"}),
        )
        with self._open(request):
            pass

    def exists(self, key: str) -> bool:
        try:
            self.size(key)
            return True
        except Exception:
            return False

    def size(self, key: str) -> int:
        endpoint = f"{self.url}/storage/v1/object/info/{quote(self.bucket)}/{quote(key, safe='/')}"
        with self._open(Request(endpoint, headers=self._headers())) as response:
            import json
            metadata = json.load(response)
        size = metadata.get("metadata", {}).get("size")
        if size is None:
            raise FileNotFoundError(key)
        return int(size)
