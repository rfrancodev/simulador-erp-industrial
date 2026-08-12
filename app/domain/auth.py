"""Pydantic schemas for authentication and authorization.

Roles follow a simple hierarchy used by the RBAC policy in
``app.security.dependencies``: ``viewer`` (read-only) < ``operator``
(write) < ``admin`` (write + delete + user management).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    role: UserRole = UserRole.VIEWER


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
