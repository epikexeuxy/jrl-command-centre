from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str  # RoleName value


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    role_name: str = ""

    @classmethod
    def from_user(cls, user) -> "UserOut":
        return cls(id=user.id, email=user.email, full_name=user.full_name,
                   is_active=user.is_active, role_name=user.role.name if user.role else "")
