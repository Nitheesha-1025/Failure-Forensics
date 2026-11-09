"""Upload validation: extension, MIME sniffing, size, safe filenames."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath

from .errors import DocumentValidationError

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"pdf", "docx", "txt", "md"})

EXTENSION_TO_MIME: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "md": "text/markdown",
}

# Accept text/plain for markdown uploads from some clients.
MIME_ALIASES: dict[str, frozenset[str]] = {
    "md": frozenset({"text/markdown", "text/plain", "text/x-markdown"}),
    "txt": frozenset({"text/plain"}),
}

_UNSAFE_NAME = re.compile(r"[^\w.\- ]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    file_type: str
    mime_type: str
    safe_original_filename: str
    display_filename: str


def extension_from_filename(filename: str) -> str:
    name = PurePath(filename or "").name
    if name.startswith(".") or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def sanitize_filename(filename: str) -> str:
    base = PurePath(filename or "upload").name
    if base in ("", ".", ".."):
        raise DocumentValidationError("Invalid filename")
    if ".." in base or "/" in base or "\\" in base:
        raise DocumentValidationError("Invalid filename")
    cleaned = _UNSAFE_NAME.sub("_", base).strip(" .")
    if not cleaned or cleaned in (".", ".."):
        raise DocumentValidationError("Invalid filename")
    return cleaned[:255]


def validate_upload_content(
    *,
    filename: str,
    content: bytes,
    max_bytes: int,
) -> ValidatedUpload:
    if not content:
        raise DocumentValidationError("File is empty")
    if len(content) > max_bytes:
        raise DocumentValidationError("File exceeds maximum upload size")

    ext = extension_from_filename(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError("Unsupported file type")

    safe_name = sanitize_filename(filename)
    detected_mime = _sniff_mime(ext, content)
    expected = EXTENSION_TO_MIME[ext]
    if not _mime_compatible(ext, detected_mime, expected):
        raise DocumentValidationError("File content does not match its type")

    return ValidatedUpload(
        file_type=ext,
        mime_type=expected,
        safe_original_filename=safe_name,
        display_filename=safe_name,
    )


def _mime_compatible(ext: str, detected: str, expected: str) -> bool:
    if detected == expected:
        return True
    aliases = MIME_ALIASES.get(ext)
    return bool(aliases and detected in aliases)


def _sniff_mime(ext: str, content: bytes) -> str:
    if ext == "pdf":
        if not content.startswith(b"%PDF-"):
            raise DocumentValidationError("Invalid or malformed PDF")
        return "application/pdf"

    if ext == "docx":
        if not content.startswith(b"PK"):
            raise DocumentValidationError("Invalid or malformed DOCX")
        try:
            with zipfile.ZipFile(BytesIO(content)) as zf:
                if "word/document.xml" not in zf.namelist():
                    raise DocumentValidationError("Invalid or malformed DOCX")
        except zipfile.BadZipFile as exc:
            raise DocumentValidationError("Invalid or malformed DOCX") from exc
        return EXTENSION_TO_MIME["docx"]

    if ext in ("txt", "md"):
        if b"\x00" in content[:8192]:
            raise DocumentValidationError("Invalid text file")
        try:
            content[:8192].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentValidationError("Text file must be UTF-8") from exc
        return EXTENSION_TO_MIME[ext]

    raise DocumentValidationError("Unsupported file type")
