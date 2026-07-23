"""Concrete repositories. Query logic that is more than trivial lives here, not in routers."""
from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Benchmark, Client, Holding, Portfolio, Role, Transaction, UploadedFile, User
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    model = Role

    def by_name(self, name: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.name == name))


class UserRepository(BaseRepository[User]):
    model = User

    def by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower()))


class ClientRepository(BaseRepository[Client]):
    model = Client

    def by_code(self, code: str) -> Client | None:
        return self.db.scalar(select(Client).where(Client.code == code))

    def search_filters(self, q: str | None):
        if not q:
            return []
        like = f"%{q}%"
        return [or_(Client.name.ilike(like), Client.code.ilike(like))]


class BenchmarkRepository(BaseRepository[Benchmark]):
    model = Benchmark


class PortfolioRepository(BaseRepository[Portfolio]):
    model = Portfolio

    def for_client(self, client_id: uuid.UUID) -> list[Portfolio]:
        return list(self.db.scalars(select(Portfolio).where(Portfolio.client_id == client_id)).all())


class HoldingRepository(BaseRepository[Holding]):
    model = Holding

    def for_portfolio(self, portfolio_id: uuid.UUID) -> list[Holding]:
        return list(self.db.scalars(
            select(Holding).where(Holding.portfolio_id == portfolio_id).order_by(Holding.name)
        ).all())

    def by_identifier(self, portfolio_id: uuid.UUID, identifier: str) -> Holding | None:
        return self.db.scalar(select(Holding).where(
            Holding.portfolio_id == portfolio_id, Holding.identifier == identifier
        ))


class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction

    def for_portfolio(self, portfolio_id: uuid.UUID) -> list[Transaction]:
        return list(self.db.scalars(
            select(Transaction).where(Transaction.portfolio_id == portfolio_id).order_by(Transaction.txn_date)
        ).all())


class UploadedFileRepository(BaseRepository[UploadedFile]):
    model = UploadedFile


def get_repositories(db: Session) -> dict:
    """Simple DI helper used by seed and tests."""
    return {
        "roles": RoleRepository(db), "users": UserRepository(db), "clients": ClientRepository(db),
        "benchmarks": BenchmarkRepository(db), "portfolios": PortfolioRepository(db),
        "holdings": HoldingRepository(db), "transactions": TransactionRepository(db),
        "uploads": UploadedFileRepository(db),
    }
