from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageProvider(Protocol):
    """Storage provider interface for Auralith media and artwork."""

    def upload(self, key: str, content: bytes, content_type: str) -> str:
        """Store binary content at key and return the stored key."""
        ...

    def open(
        self, key: str, start: int | None = None, end: int | None = None
    ) -> BinaryIO:
        """Open a readable stream for the key with optional byte range."""
        ...

    def delete(self, key: str) -> None:
        """Delete object identified by key."""
        ...

    def exists(self, key: str) -> bool:
        """Check whether object identified by key exists."""
        ...

    def size(self, key: str) -> int:
        """Return the size in bytes of the stored object."""
        ...
