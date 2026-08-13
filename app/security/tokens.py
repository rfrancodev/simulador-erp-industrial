"""JWT token creation and validation (HS256, signed with SECRET_KEY)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import jwt

_ALGORITHM = "HS256"
_SECRET_MIN_BYTES = 32


def _secret() -> str:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY must be set")
    if len(secret.encode("utf-8")) < _SECRET_MIN_BYTES:
        raise RuntimeError(
            f"SECRET_KEY must contain at least {_SECRET_MIN_BYTES} bytes"
        )
    return secret


def validate_secret_key() -> None:
    """Fail fast when the application is configured with an unsafe JWT key."""
    _secret()


def token_expiry_minutes() -> int:
    return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


def create_access_token(subject: str) -> str:
    """Create a signed access token embedding the user identity."""
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=token_expiry_minutes()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a token, raising ``jwt.PyJWTError`` on failure."""
    return jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
