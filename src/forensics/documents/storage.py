"""Pluggable binary storage for uploaded documents."""

from __future__ import annotations

import contextlib
import re
from abc import ABC, abstractmethod
from pathlib import Path

from .errors import DocumentStorageError, DocumentValidationError

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def build_storage_key(user_id: str, document_id: str) -> str:
    if not _UUID_RE.match(user_id) or not _UUID_RE.match(document_id):
        raise DocumentValidationError("Invalid storage identifiers")
    return f"{user_id}/{document_id}"


class DocumentStorage(ABC):
    @abstractmethod
    def save(self, *, user_id: str, document_id: str, content: bytes) -> str:
        """Persist bytes; return opaque storage key."""

    @abstractmethod
    def read(self, storage_key: str) -> bytes:
        """Load bytes by storage key."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Remove stored object if present."""


class LocalDocumentStorage(DocumentStorage):
    def __init__(self, base_dir: Path):
        self._base = base_dir.resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _path_for_key(self, storage_key: str) -> Path:
        key = storage_key.replace("\\", "/").strip("/")
        if ".." in key.split("/"):
            raise DocumentStorageError("Invalid storage key")
        parts = key.split("/")
        if len(parts) != 2:
            raise DocumentStorageError("Invalid storage key")
        user_id, document_id = parts
        build_storage_key(user_id, document_id)  # validates UUID shape
        target = (self._base / user_id / document_id).resolve()
        try:
            target.relative_to(self._base)
        except ValueError as exc:
            raise DocumentStorageError("Invalid storage path") from exc
        return target

    def save(self, *, user_id: str, document_id: str, content: bytes) -> str:
        key = build_storage_key(user_id, document_id)
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(content)
        except OSError as exc:
            raise DocumentStorageError("Failed to store document") from exc
        return key

    def read(self, storage_key: str) -> bytes:
        path = self._path_for_key(storage_key)
        if not path.is_file():
            raise DocumentStorageError("Document file not found")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise DocumentStorageError("Failed to read document") from exc

    def delete(self, storage_key: str) -> None:
        path = self._path_for_key(storage_key)
        if not path.is_file():
            return
        try:
            path.unlink()
        except OSError as exc:
            raise DocumentStorageError("Failed to delete document file") from exc
        parent = path.parent
        if parent.is_dir() and not any(parent.iterdir()):
            with contextlib.suppress(OSError):
                parent.rmdir()
