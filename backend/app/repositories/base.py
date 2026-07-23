"""Generic repository: typed CRUD over a SQLAlchemy model."""
from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def get(self, id_: uuid.UUID) -> ModelT | None:
        return self.db.get(self.model, id_)

    def list(self, *, limit: int = 20, offset: int = 0, filters: list[Any] | None = None,
             order_by: Any = None) -> tuple[list[ModelT], int]:
        stmt = select(self.model)
        count_stmt = select(func.count()).select_from(self.model)
        for f in filters or []:
            stmt = stmt.where(f)
            count_stmt = count_stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        total = self.db.scalar(count_stmt) or 0
        items = list(self.db.scalars(stmt.limit(limit).offset(offset)).all())
        return items, total

    def create(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, obj: ModelT, data: dict[str, Any]) -> ModelT:
        for key, value in data.items():
            setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()
