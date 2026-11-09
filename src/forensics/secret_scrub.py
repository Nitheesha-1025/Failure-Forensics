"""Redact likely secrets from strings returned to clients or stored in metadata."""

from __future__ import annotations

import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|authorization|bearer|x-goog-api-key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"(?i)AIza[0-9A-Za-z\-_]{20,}"),
)


def scrub_secrets_for_client(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[redacted]", out)
    return out
