from __future__ import annotations

import uuid

import jwt as pyjwt
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import AuthError
from app.core.rate_limit import limiter
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.db.session import get_db
from app.models import User
from app.repositories.repositories import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = UserRepository(db).by_email(body.email)
    if user is None or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise AuthError("Invalid email or password")
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.name),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("20/minute")
def refresh(request: Request, body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except pyjwt.PyJWTError as exc:
        raise AuthError("Invalid or expired refresh token") from exc
    user = UserRepository(db).get(uuid.UUID(str(payload["sub"])))
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.name),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.from_user(user)
