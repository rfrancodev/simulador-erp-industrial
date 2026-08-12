"""Authentication service — user registration and credential verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from logging import getLogger

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateEntityError
from app.domain.auth import UserCreate
from app.domain.entities import User
from app.repositories.user_repository import UserRepository
from app.security.passwords import hash_password, verify_password

logger = getLogger(__name__)

# Constant-time login: always verify against a valid hash so response timing
# does not reveal whether a username exists (L-22).
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-constant-time-login")

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


class AuthService:
    def __init__(self, session: Session):
        self._session = session
        self.users = UserRepository(session)

    def create_user(self, data: UserCreate) -> User:
        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
            role=data.role.value,
        )
        try:
            created = self.users.add(user)
            self._session.commit()
            logger.info("User %s created with role %s", created.username, created.role)
            return created
        except IntegrityError:
            self._session.rollback()
            raise DuplicateEntityError("User", data.username) from None

    def authenticate(self, username: str, password: str) -> User:
        user = self.users.get_by_username(username)
        stored_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
        password_ok = verify_password(password, stored_hash)

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if self._is_locked(user):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account temporarily locked. Please try again later.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not password_ok:
            self._register_failed_attempt(user)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        self._reset_failed_attempts(user)
        return user

    def _is_locked(self, user: User) -> bool:
        if user.locked_until is None:
            return False
        locked = user.locked_until
        if locked.tzinfo is None:
            # SQLite does not preserve timezone info; assume UTC.
            locked = locked.replace(tzinfo=UTC)
        return locked > datetime.now(UTC)

    def _register_failed_attempt(self, user: User) -> None:
        user.failed_attempts = (user.failed_attempts or 0) + 1
        if user.failed_attempts >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=_LOCKOUT_MINUTES)
            user.failed_attempts = 0
            logger.warning(
                "User %s locked for %s minutes after %s failed attempts",
                user.username,
                _LOCKOUT_MINUTES,
                _MAX_FAILED_ATTEMPTS,
            )
        self._session.commit()

    def _reset_failed_attempts(self, user: User) -> None:
        if user.failed_attempts or user.locked_until:
            user.failed_attempts = 0
            user.locked_until = None
            self._session.commit()
