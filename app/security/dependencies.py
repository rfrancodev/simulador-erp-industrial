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


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    scheme, _, param = authorization.partition(" ")
    if scheme.lower() != "bearer" or not param:
        return None
    return param


def _user_from_token(token: str, session: Session) -> User:
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


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(session_dependency),
) -> User:
    """Resolve the authenticated user from the JWT bearer token."""
    return _user_from_token(token, session)


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


def require_dashboard_access(
    request: Request,
    session: Session = Depends(session_dependency),
) -> User:
    """Authenticate dashboard browser requests (read-only) via HttpOnly cookie.

    The token is set on login and accepted only for GET/HEAD/OPTIONS requests, so
    mutating API endpoints are not exposed to cross-site request forgery.
    """
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="Method not allowed for dashboard session",
        )

    token = request.cookies.get("access_token") or _bearer_token(request)
    if not token:
        raise _credentials_error()

    user = _user_from_token(token, session)
    role = _resolve_role(user)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    request.state.user = user
    return user


def require_admin_access(
    request: Request,
    session: Session = Depends(session_dependency),
) -> User:
    """Authenticate admin-only resources (e.g. API docs) via cookie or bearer
    token and require the ``admin`` role.

    Non-admin users receive ``403 Forbidden``; unauthenticated requests receive
    the standard ``401`` credentials error, mirroring the dashboard behavior.
    """
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="Method not allowed",
        )

    token = request.cookies.get("access_token") or _bearer_token(request)
    if not token:
        raise _credentials_error()

    user = _user_from_token(token, session)
    if _resolve_role(user) != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    request.state.user = user
    return user
