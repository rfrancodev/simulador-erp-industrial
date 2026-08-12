"""REST API router for authentication and token issuance."""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database.connection import session_dependency
from app.domain.auth import Token, UserCreate, UserOut, UserRole
from app.domain.entities import User
from app.security.dependencies import get_current_user, require_roles
from app.security.tokens import create_access_token, token_expiry_minutes
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _svc(session: Session = Depends(session_dependency)) -> AuthService:
    return AuthService(session)


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    svc: AuthService = Depends(_svc),
):
    user = svc.authenticate(form.username, form.password)
    token = create_access_token(subject=user.username)
    return Token(
        access_token=token,
        expires_in=token_expiry_minutes() * 60,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/register", response_model=UserOut, status_code=201)
def register(
    data: UserCreate,
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
    svc: AuthService = Depends(_svc),
):
    return svc.create_user(data)
