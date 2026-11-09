"""Extract normalized UTF-8 text from supported document types."""

from __future__ import annotations

from io import BytesIO

from docx import Document as DocxDocument
from pypdf import PdfReader

from .errors import DocumentParseError


def extract_text(*, file_type: str, content: bytes) -> str:
    if file_type == "pdf":
        return _parse_pdf(content)
    if file_type == "docx":
        return _parse_docx(content)
    if file_type in ("txt", "md"):
        return _parse_text(content)
    raise DocumentParseError(f"Unsupported file type: {file_type}")


def _parse_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text.strip())
        if not parts:
            raise DocumentParseError("PDF contains no extractable text")
        return "\n\n".join(parts)
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("Failed to parse PDF") from exc


def _parse_docx(content: bytes) -> str:
    try:
        doc = DocxDocument(BytesIO(content))
        parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if not parts:
            raise DocumentParseError("DOCX contains no extractable text")
        return "\n".join(parts)
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("Failed to parse DOCX") from exc


def _parse_text(content: bytes) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentParseError("Text file must be UTF-8") from exc
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise DocumentParseError("Text file is empty")
    return normalized
