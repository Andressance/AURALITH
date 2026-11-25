"""Storage fan-out across several backends.

Providers are ordered. Uploads go to every provider (a replica per backend) and
reads try them in turn, so one dead or full backend does not take the library
down. With mirroring disabled the first provider that accepts the write wins and
the rest are only a fallback for later reads.

All providers share the same key namespace, so a key stored by any of them can be
served by any other without touching the database.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class MultiStorageProvider:
    def __init__(self, providers, mirror: bool = True):
        providers = list(providers)
        if not providers:
            raise RuntimeError("MultiStorageProvider needs at least one provider")
        self.providers = providers
        self.mirror = bool(mirror)
        self._hints: dict[str, int] = {}
        self._lock = threading.Lock()

    def _ordered(self, key: str):
        with self._lock:
            hint = self._hints.get(key, 0)
        if not 0 <= hint < len(self.providers):
            hint = 0
        preferred = self.providers[hint]
        return [preferred] + [
            provider for index, provider in enumerate(self.providers) if index != hint
        ]

    def _remember(self, key: str, provider) -> None:
        try:
            index = self.providers.index(provider)
        except ValueError:
            return
        with self._lock:
            self._hints[key] = index

    def upload(self, key: str, content: bytes, content_type: str) -> str:
        failures = []
        written = 0
        for provider in self.providers:
            try:
                provider.upload(key, content, content_type)
            except Exception as error:  # noqa: BLE001 - one backend must not block the rest
                failures.append(error)
                logger.warning(
                    "Storage provider %s could not store %s: %s",
                    type(provider).__name__,
                    key,
                    error,
                )
                continue
            written += 1
            self._remember(key, provider)
            if not self.mirror:
                break
        if not written:
            if failures:
                raise failures[0]
            raise RuntimeError(f"No storage provider accepted {key}")
        return key

    def open(self, key: str, start: int | None = None, end: int | None = None):
        last_error = None
        for provider in self._ordered(key):
            try:
                stream = provider.open(key, start=start, end=end)
            except FileNotFoundError:
                continue
            except Exception as error:  # noqa: BLE001 - try the replica
                last_error = error
                logger.warning(
                    "Storage provider %s failed to open %s: %s",
                    type(provider).__name__,
                    key,
                    error,
                )
                continue
            self._remember(key, provider)
            return stream
        if last_error is not None:
            raise last_error
        raise FileNotFoundError(key)

    def size(self, key: str) -> int:
        last_error = None
        for provider in self._ordered(key):
            try:
                size = provider.size(key)
            except FileNotFoundError:
                continue
            except Exception as error:  # noqa: BLE001 - try the replica
                last_error = error
                continue
            self._remember(key, provider)
            return size
        if last_error is not None:
            raise last_error
        raise FileNotFoundError(key)

    def exists(self, key: str) -> bool:
        last_error = None
        for provider in self._ordered(key):
            try:
                if provider.exists(key):
                    self._remember(key, provider)
                    return True
            except Exception as error:  # noqa: BLE001 - try the replica
                last_error = error
        if last_error is not None:
            raise last_error
        return False

    def delete(self, key: str) -> None:
        first_error = None
        for provider in self.providers:
            try:
                provider.delete(key)
            except FileNotFoundError:
                continue
            except Exception as error:  # noqa: BLE001 - delete everywhere we can
                if first_error is None:
                    first_error = error
                logger.warning(
                    "Storage provider %s could not delete %s: %s",
                    type(provider).__name__,
                    key,
                    error,
                )
        with self._lock:
            self._hints.pop(key, None)
        if first_error is not None:
            raise first_error
