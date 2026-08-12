"""Security dependencies for FastAPI — authentication and authorization."""

from __future__ import annotations

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database.connection import session_dependency
from app.domain.auth import UserRole
from app.domain.entities import User
from app.repositories.user_repository import UserRepository
from app.security.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Role hierarchy for method-based authorization (higher = more privileges).
_ROLE_LEVEL = {
    UserRole.VIEWER: 0,
    UserRole.OPERATOR: 1,
    UserRole.ADMIN: 2,
}

# Minimum role required to perform each HTTP method.
_METHOD_MIN_ROLE = {
    "GET": UserRole.VIEWER,
    "HEAD": UserRole.VIEWER,
    "OPTIONS": UserRole.VIEWER,
    "POST": UserRole.OPERATOR,
    "PUT": UserRole.OPERATOR,
    "PATCH": UserRole.OPERATOR,
    "DELETE": UserRole.ADMIN,
}


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_role(user: User) -> UserRole | None:
    """Safely map a user's stored role to the enum (None if invalid/corrupted)."""
    try:
        return UserRole(user.role)
    except (ValueError, TypeError):
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(session_dependency),
) -> User:
    """Resolve the authenticated user from the JWT bearer token."""
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise _credentials_error()
    except pyjwt.PyJWTError:
        raise _credentials_error() from None

    user = UserRepository(session).get_by_username(username)
    if user is None or not user.is_active:
        raise _credentials_error()
    return user


def require_roles(*roles: UserRole):
    """Return a dependency that only allows the given roles."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if _resolve_role(user) not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return checker


def require_api_access(
    request: Request, user: User = Depends(get_current_user)
) -> User:
    """Router-level dependency enforcing method-based RBAC.

    - GET/HEAD/OPTIONS  -> viewer or above
    - POST/PUT/PATCH    -> operator or above
    - DELETE            -> admin only
    """
    required = _METHOD_MIN_ROLE.get(request.method, UserRole.ADMIN)
    role = _resolve_role(user)
    if role is None or _ROLE_LEVEL[role] < _ROLE_LEVEL[required]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return user
