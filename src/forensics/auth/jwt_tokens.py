"""JWT access token creation and validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError


class TokenError(Exception):
    pass


def create_access_token(
    *,
    subject: str,
    secret: str,
    algorithm: str = "HS256",
    expires_minutes: int = 60,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "type": "access",
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(
    token: str,
    *,
    secret: str,
    algorithm: str = "HS256",
) -> str:
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except InvalidTokenError as exc:
        raise TokenError("invalid or expired token") from exc
    if payload.get("type") != "access":
        raise TokenError("invalid token type")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise TokenError("invalid token subject")
    return sub
