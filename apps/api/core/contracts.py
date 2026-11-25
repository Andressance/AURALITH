from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import BinaryIO, Protocol


class StorageObject(Protocol):
    key: str
    size: int
    content_type: str


class StorageProvider(ABC):
    @abstractmethod
    def upload(self, key: str, content: bytes, content_type: str) -> str:
        """Store an object and return its provider-specific key."""

    @abstractmethod
    def open(self, key: str) -> BinaryIO:
        """Open an object for reading."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete an object if it exists."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return whether an object exists."""

    @abstractmethod
    def size(self, key: str) -> int:
        """Return the object size in bytes."""


class DatabaseProvider(ABC):
    @abstractmethod
    def create_session(self) -> AbstractContextManager[object]:
        """Create a unit of work."""

    @abstractmethod
    def dispose(self) -> None:
        """Close provider resources."""
