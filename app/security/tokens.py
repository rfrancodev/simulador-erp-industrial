"""JWT token creation and validation (HS256, signed with SECRET_KEY)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

import jwt

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_SECRET_MIN_BYTES = 32

_warned_weak_secret = False


def _secret() -> str:
    global _warned_weak_secret
    secret = os.getenv("SECRET_KEY", "change-me-in-production")
    if len(secret.encode("utf-8")) < _SECRET_MIN_BYTES and not _warned_weak_secret:
        _warned_weak_secret = True
        logger.warning(
            "SECRET_KEY is shorter than %s bytes; set a stronger key in production",
            _SECRET_MIN_BYTES,
        )
    return secret


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
