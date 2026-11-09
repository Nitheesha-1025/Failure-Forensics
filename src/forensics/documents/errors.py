"""Document layer exceptions."""

from __future__ import annotations


class DocumentError(Exception):
    pass


class DocumentValidationError(DocumentError):
    pass


class DocumentStorageError(DocumentError):
    pass


class DocumentParseError(DocumentError):
    pass


class DocumentNotFoundError(DocumentError):
    pass
