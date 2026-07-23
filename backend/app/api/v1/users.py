from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.constants import RoleName
from app.core.exceptions import ConflictError, ValidationFailure
from app.core.security import hash_password
from app.db.session import get_db
from app.models import User
from app.repositories.repositories import RoleRepository, UserRepository
from app.schemas.auth import UserCreate, UserOut
from app.schemas.common import Page

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_roles(RoleName.ADMIN))])


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    users = UserRepository(db)
    if users.by_email(body.email) is not None:
        raise ConflictError("A user with this email already exists")
    role = RoleRepository(db).by_name(body.role)
    if role is None:
        raise ValidationFailure(f"Unknown role '{body.role}'")
    user = users.create(User(email=body.email.lower(), full_name=body.full_name,
                             hashed_password=hash_password(body.password), role_id=role.id))
    return UserOut.from_user(user)


@router.get("", response_model=Page[UserOut])
def list_users(limit: int = Query(20, le=100), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db)) -> Page[UserOut]:
    items, total = UserRepository(db).list(limit=limit, offset=offset, order_by=User.created_at)
    return Page(items=[UserOut.from_user(u) for u in items], total=total, limit=limit, offset=offset)
