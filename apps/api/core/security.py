import ipaddress
import os
import threading
import time
from collections import OrderedDict, deque
from math import ceil


COMMON_PASSWORDS = {
    "change-me",
    "changeme",
    "password",
    "password123",
    "test-password",
    "admin",
}


def is_strong_owner_password(password: str) -> bool:
    if len(password) < 12:
        return False
    normalized = password.lower().strip()
    if normalized in COMMON_PASSWORDS:
        return False
    if any(marker in normalized for marker in ("changeme", "change-me")):
        return False
    if not any(character.islower() for character in password):
        return False
    if not any(character.isupper() for character in password):
        return False
    if not any(character.isdigit() for character in password):
        return False
    return True


def build_allowed_origins(configured: str) -> set[str]:
    origins = {
        origin.strip().rstrip("/")
        for origin in configured.split(",")
        if origin.strip()
    }
    if os.getenv("AURALITH_ENV", "production").lower() == "development":
        origins.update({"http://localhost:5173", "http://127.0.0.1:5173"})
    return origins


def is_allowed_origin(origin: str, allowed_origins: set[str]) -> bool:
    normalized = origin.strip().rstrip("/")
    if normalized in allowed_origins:
        return True
    if os.getenv("AURALITH_ALLOW_VERCEL_ORIGINS", "false").lower() == "true":
        if normalized.startswith("https://") and normalized.endswith(".vercel.app"):
            return True
    return False


class LoginRateLimiter:
    def __init__(
        self,
        limit: int = 5,
        window_seconds: int = 15 * 60,
        max_keys: int = 4096,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self.attempts: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self.attempts.get(key)
            if bucket is None:
                if len(self.attempts) >= self.max_keys:
                    self.attempts.popitem(last=False)
                bucket = deque()
                self.attempts[key] = bucket
            else:
                self.attempts.move_to_end(key)
            while bucket and now - bucket[0] >= self.window_seconds:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self.attempts.pop(key, None)

    def retry_after(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            bucket = self.attempts.get(key)
            if not bucket:
                return 1
            while bucket and now - bucket[0] >= self.window_seconds:
                bucket.popleft()
            return max(1, ceil(self.window_seconds - (now - bucket[0]))) if len(bucket) >= self.limit else 1


class SlidingWindowRateLimiter:
    def __init__(self, max_keys: int = 4096):
        self.max_keys = max_keys
        self.attempts: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> int:
        now = time.monotonic()
        with self._lock:
            bucket = self.attempts.get(key)
            if bucket is None:
                if len(self.attempts) >= self.max_keys:
                    self.attempts.popitem(last=False)
                bucket = deque()
                self.attempts[key] = bucket
            else:
                self.attempts.move_to_end(key)
            while bucket and now - bucket[0] >= window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return max(1, ceil(window_seconds - (now - bucket[0])))
            bucket.append(now)
            return 0


def _trusted_proxy_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    configured = os.getenv("AURALITH_TRUSTED_PROXIES", "127.0.0.1/32,::1/128")
    try:
        return tuple(
            ipaddress.ip_network(value.strip(), strict=False)
            for value in configured.split(",")
            if value.strip()
        )
    except ValueError as error:
        raise RuntimeError("AURALITH_TRUSTED_PROXIES must contain valid IPs or CIDRs") from error


def get_client_ip(request) -> str:
    client = getattr(request, "client", None)
    peer = getattr(client, "host", None) or "unknown"
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    trusted_networks = _trusted_proxy_networks()
    if not any(peer_address in network for network in trusted_networks):
        return str(peer_address)

    forwarded = request.headers.get("x-forwarded-for", "")
    chain = []
    for value in forwarded.split(","):
        try:
            chain.append(ipaddress.ip_address(value.strip()))
        except ValueError:
            continue
    for address in reversed(chain):
        if not any(address in network for network in trusted_networks):
            return str(address)
    return str(peer_address)


login_rate_limiter = LoginRateLimiter()
