"""Authenticated document upload and management."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user, get_db
from ..db.models import User
from ..documents.errors import (
    DocumentNotFoundError,
    DocumentParseError,
    DocumentStorageError,
    DocumentValidationError,
)
from ..documents.schemas import DocumentListResponse, DocumentPublic, DocumentTextResponse
from ..documents.service import DocumentService, total_pages

router = APIRouter(prefix="/v1/documents", tags=["documents"])

_MAX_PAGE_SIZE = 100


def _document_service(request: Request) -> DocumentService:
    service = getattr(request.app.state, "document_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="document storage is not configured",
        )
    return cast(DocumentService, service)


async def _read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum upload size",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", response_model=DocumentPublic, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File(...)],
) -> DocumentPublic:
    service = _document_service(request)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    content = await _read_upload_limited(file, service.max_upload_bytes)
    try:
        doc = service.upload(
            db,
            user=current_user,
            filename=file.filename,
            content=content,
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentStorageError as exc:
        raise HTTPException(status_code=500, detail="Failed to store document") from exc
    return DocumentPublic.model_validate(doc)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=_MAX_PAGE_SIZE),
) -> DocumentListResponse:
    service = _document_service(request)
    items, total = service.list_for_user(
        db, user=current_user, page=page, page_size=page_size
    )
    return DocumentListResponse(
        items=[DocumentPublic.model_validate(d) for d in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages(total, page_size),
    )


@router.get("/{document_id}", response_model=DocumentPublic)
def get_document(
    document_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentPublic:
    service = _document_service(request)
    try:
        doc = service.get_owned(db, user=current_user, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    return DocumentPublic.model_validate(doc)


@router.get("/{document_id}/text", response_model=DocumentTextResponse)
def get_document_text(
    document_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentTextResponse:
    service = _document_service(request)
    try:
        text = service.extract_document_text(
            db, user=current_user, document_id=document_id
        )
        doc = service.get_owned(db, user=current_user, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except DocumentParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DocumentTextResponse(
        document_id=doc.id,
        file_type=doc.file_type,
        text=text,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    service = _document_service(request)
    try:
        service.delete(db, user=current_user, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except DocumentStorageError as exc:
        raise HTTPException(status_code=500, detail="Failed to delete document") from exc
