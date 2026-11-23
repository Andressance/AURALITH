import os
import time
from collections import defaultdict, deque


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


class LoginRateLimiter:
    def __init__(self, limit: int = 5, window_seconds: int = 15 * 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self.attempts: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self.attempts[key]
        while bucket and now - bucket[0] >= self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True

    def reset(self, key: str) -> None:
        self.attempts.pop(key, None)


login_rate_limiter = LoginRateLimiter()
