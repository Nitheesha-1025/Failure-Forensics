"""FastAPI dependencies for authentication."""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db.models import User
from .jwt_tokens import TokenError, decode_access_token

if TYPE_CHECKING:
    from ..config import Settings

_bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database is not configured",
        )
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_db_optional(request: Request) -> Generator[Session | None, None, None]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        yield None
        return
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_current_user_when_database_enabled(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session | None, Depends(get_db_optional)],
) -> User | None:
    """When PostgreSQL auth is wired, require a valid user; otherwise allow anonymous."""
    if db is None:
        return None
    return get_current_user(request, credentials, db)


def _auth_settings(request: Request) -> Settings:
    return cast("Settings", request.app.state.settings)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    settings = _auth_settings(request)
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="authentication is not configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = decode_access_token(
            credentials.credentials,
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
