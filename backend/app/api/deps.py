"""FastAPI dependencies: current user extraction and role-based access control."""
from __future__ import annotations

import uuid

import jwt as pyjwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.constants import RoleName
from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User
from app.repositories.repositories import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthError("Missing bearer token")
    try:
        payload = decode_token(credentials.credentials, "access")
    except pyjwt.PyJWTError as exc:
        raise AuthError("Invalid or expired token") from exc
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (ValueError, TypeError) as exc:
        raise AuthError("Malformed token subject") from exc
    user = UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return user


def require_roles(*roles: RoleName):
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role.name not in allowed:
            raise ForbiddenError(f"Requires one of roles: {', '.join(sorted(allowed))}")
        return user

    return checker


# Common role groups
ANY_USER = Depends(get_current_user)
WEALTH_WRITE = Depends(require_roles(RoleName.ADMIN, RoleName.WEALTH_MANAGER))
ADMIN_ONLY = Depends(require_roles(RoleName.ADMIN))
