from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.constants import RoleName
from app.core.exceptions import NotFoundError, ValidationFailure
from app.db.session import get_db
from app.models import Benchmark, Holding, Portfolio, Transaction
from app.repositories.repositories import (
    BenchmarkRepository,
    ClientRepository,
    HoldingRepository,
    PortfolioRepository,
    TransactionRepository,
)
from app.schemas.common import Message, Page
from app.schemas.wealth import (
    BenchmarkOut,
    HoldingCreate,
    HoldingOut,
    HoldingUpdate,
    PortfolioCreate,
    PortfolioOut,
    PortfolioUpdate,
    TransactionCreate,
    TransactionOut,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])

WRITE = Depends(require_roles(RoleName.ADMIN, RoleName.WEALTH_MANAGER))
READ = Depends(get_current_user)


def _get_portfolio(db: Session, portfolio_id: uuid.UUID) -> Portfolio:
    p = PortfolioRepository(db).get(portfolio_id)
    if p is None:
        raise NotFoundError("Portfolio not found")
    return p


@router.post("", response_model=PortfolioOut, status_code=201, dependencies=[WRITE])
def create_portfolio(body: PortfolioCreate, db: Session = Depends(get_db)) -> Portfolio:
    if ClientRepository(db).get(body.client_id) is None:
        raise ValidationFailure("client_id does not reference an existing client")
    if body.benchmark_id and BenchmarkRepository(db).get(body.benchmark_id) is None:
        raise ValidationFailure("benchmark_id does not reference an existing benchmark")
    return PortfolioRepository(db).create(Portfolio(**body.model_dump()))


@router.get("", response_model=Page[PortfolioOut], dependencies=[READ])
def list_portfolios(limit: int = Query(20, le=100), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db)) -> Page:
    items, total = PortfolioRepository(db).list(limit=limit, offset=offset, order_by=Portfolio.created_at)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/benchmarks", response_model=list[BenchmarkOut], dependencies=[READ])
def list_benchmarks(db: Session = Depends(get_db)):
    items, _ = BenchmarkRepository(db).list(limit=100, order_by=Benchmark.name)
    return items


@router.get("/{portfolio_id}", response_model=PortfolioOut, dependencies=[READ])
def get_portfolio(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> Portfolio:
    return _get_portfolio(db, portfolio_id)


@router.patch("/{portfolio_id}", response_model=PortfolioOut, dependencies=[WRITE])
def update_portfolio(portfolio_id: uuid.UUID, body: PortfolioUpdate, db: Session = Depends(get_db)) -> Portfolio:
    p = _get_portfolio(db, portfolio_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("benchmark_id") and BenchmarkRepository(db).get(data["benchmark_id"]) is None:
        raise ValidationFailure("benchmark_id does not reference an existing benchmark")
    return PortfolioRepository(db).update(p, data)


@router.delete("/{portfolio_id}", response_model=Message, dependencies=[Depends(require_roles(RoleName.ADMIN))])
def delete_portfolio(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> Message:
    p = _get_portfolio(db, portfolio_id)
    PortfolioRepository(db).delete(p)
    return Message(message="Portfolio deleted")


# ---------------- Holdings ----------------
@router.get("/{portfolio_id}/holdings", response_model=list[HoldingOut], dependencies=[READ])
def list_holdings(portfolio_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_portfolio(db, portfolio_id)
    return HoldingRepository(db).for_portfolio(portfolio_id)


@router.post("/{portfolio_id}/holdings", response_model=HoldingOut, status_code=201, dependencies=[WRITE])
def create_holding(portfolio_id: uuid.UUID, body: HoldingCreate, db: Session = Depends(get_db)) -> Holding:
    _get_portfolio(db, portfolio_id)
    return HoldingRepository(db).create(Holding(portfolio_id=portfolio_id, **body.model_dump()))


@router.patch("/{portfolio_id}/holdings/{holding_id}", response_model=HoldingOut, dependencies=[WRITE])
def update_holding(portfolio_id: uuid.UUID, holding_id: uuid.UUID, body: HoldingUpdate,
                   db: Session = Depends(get_db)) -> Holding:
    repo = HoldingRepository(db)
    h = repo.get(holding_id)
    if h is None or h.portfolio_id != portfolio_id:
        raise NotFoundError("Holding not found in this portfolio")
    return repo.update(h, body.model_dump(exclude_unset=True))


@router.delete("/{portfolio_id}/holdings/{holding_id}", response_model=Message, dependencies=[WRITE])
def delete_holding(portfolio_id: uuid.UUID, holding_id: uuid.UUID, db: Session = Depends(get_db)) -> Message:
    repo = HoldingRepository(db)
    h = repo.get(holding_id)
    if h is None or h.portfolio_id != portfolio_id:
        raise NotFoundError("Holding not found in this portfolio")
    repo.delete(h)
    return Message(message="Holding deleted")


# ---------------- Transactions ----------------
@router.get("/{portfolio_id}/transactions", response_model=Page[TransactionOut], dependencies=[READ])
def list_transactions(portfolio_id: uuid.UUID, limit: int = Query(50, le=200), offset: int = Query(0, ge=0),
                      db: Session = Depends(get_db)) -> Page:
    _get_portfolio(db, portfolio_id)
    repo = TransactionRepository(db)
    items, total = repo.list(limit=limit, offset=offset,
                             filters=[Transaction.portfolio_id == portfolio_id],
                             order_by=Transaction.txn_date.desc())
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/{portfolio_id}/transactions", response_model=TransactionOut, status_code=201, dependencies=[WRITE])
def create_transaction(portfolio_id: uuid.UUID, body: TransactionCreate, db: Session = Depends(get_db)) -> Transaction:
    _get_portfolio(db, portfolio_id)
    data = body.model_dump()
    holding_id = data.pop("holding_id", None)
    if holding_id is not None:
        h = HoldingRepository(db).get(holding_id)
        if h is None or h.portfolio_id != portfolio_id:
            raise ValidationFailure("holding_id does not belong to this portfolio")
    return TransactionRepository(db).create(Transaction(portfolio_id=portfolio_id, holding_id=holding_id, **data))


@router.delete("/{portfolio_id}/transactions/{txn_id}", response_model=Message, dependencies=[WRITE])
def delete_transaction(portfolio_id: uuid.UUID, txn_id: uuid.UUID, db: Session = Depends(get_db)) -> Message:
    repo = TransactionRepository(db)
    t = repo.get(txn_id)
    if t is None or t.portfolio_id != portfolio_id:
        raise NotFoundError("Transaction not found in this portfolio")
    repo.delete(t)
    return Message(message="Transaction deleted")
