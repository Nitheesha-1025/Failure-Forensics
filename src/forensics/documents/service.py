"""Document business logic: upload, list, fetch, delete, text extraction."""

from __future__ import annotations

import contextlib
import math
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Document, ProcessingStatus, User
from .errors import (
    DocumentNotFoundError,
    DocumentParseError,
    DocumentStorageError,
)
from .parsers import extract_text
from .storage import DocumentStorage
from .validation import validate_upload_content

if TYPE_CHECKING:
    from ..config import Settings


class DocumentService:
    def __init__(self, storage: DocumentStorage, settings: Settings):
        self._storage = storage
        self._settings = settings

    @property
    def max_upload_bytes(self) -> int:
        return self._settings.max_upload_size_mb * 1024 * 1024

    def upload(
        self,
        db: Session,
        *,
        user: User,
        filename: str,
        content: bytes,
    ) -> Document:
        validated = validate_upload_content(
            filename=filename,
            content=content,
            max_bytes=self.max_upload_bytes,
        )
        document_id = str(uuid.uuid4())
        storage_key = self._storage.save(
            user_id=user.id,
            document_id=document_id,
            content=content,
        )
        doc = Document(
            id=document_id,
            user_id=user.id,
            filename=validated.display_filename,
            original_filename=validated.safe_original_filename,
            file_type=validated.file_type,
            mime_type=validated.mime_type,
            file_size=len(content),
            storage_key=storage_key,
            processing_status=ProcessingStatus.UPLOADED.value,
        )
        db.add(doc)
        try:
            db.commit()
        except Exception:
            db.rollback()
            with contextlib.suppress(DocumentStorageError):
                self._storage.delete(storage_key)
            raise
        db.refresh(doc)
        return doc

    def list_for_user(
        self,
        db: Session,
        *,
        user: User,
        page: int,
        page_size: int,
    ) -> tuple[list[Document], int]:
        total = db.scalar(
            select(func.count()).select_from(Document).where(Document.user_id == user.id)
        )
        total_int = int(total or 0)
        offset = (page - 1) * page_size
        rows = db.scalars(
            select(Document)
            .where(Document.user_id == user.id)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
        return list(rows), total_int

    def get_owned(self, db: Session, *, user: User, document_id: str) -> Document:
        doc = db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user.id,
            )
        )
        if doc is None:
            raise DocumentNotFoundError()
        return doc

    def get_owned_for_update(
        self, db: Session, *, user: User, document_id: str
    ) -> Document:
        """Lock the document row for the duration of the current transaction."""
        doc = db.scalar(
            select(Document)
            .where(
                Document.id == document_id,
                Document.user_id == user.id,
            )
            .with_for_update()
        )
        if doc is None:
            raise DocumentNotFoundError()
        return doc

    def delete(self, db: Session, *, user: User, document_id: str) -> None:
        doc = self.get_owned(db, user=user, document_id=document_id)
        storage_key = doc.storage_key
        with contextlib.suppress(DocumentStorageError):
            self._storage.delete(storage_key)
        db.delete(doc)
        db.commit()

    def extract_document_text(self, db: Session, *, user: User, document_id: str) -> str:
        doc = self.get_owned(db, user=user, document_id=document_id)
        try:
            content = self._storage.read(doc.storage_key)
        except DocumentStorageError as exc:
            raise DocumentParseError("Document file is unavailable") from exc
        return extract_text(file_type=doc.file_type, content=content)


def total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return max(1, math.ceil(total / page_size))
