from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.constants import RoleName
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import Client
from app.repositories.repositories import ClientRepository, PortfolioRepository
from app.schemas.common import Message, Page
from app.schemas.wealth import ClientCreate, ClientOut, ClientUpdate, PortfolioOut

router = APIRouter(prefix="/clients", tags=["clients"])

WRITE = Depends(require_roles(RoleName.ADMIN, RoleName.WEALTH_MANAGER))


@router.post("", response_model=ClientOut, status_code=201, dependencies=[WRITE])
def create_client(body: ClientCreate, db: Session = Depends(get_db)) -> Client:
    repo = ClientRepository(db)
    if repo.by_code(body.code) is not None:
        raise ConflictError(f"Client code '{body.code}' already exists")
    return repo.create(Client(**body.model_dump()))


@router.get("", response_model=Page[ClientOut], dependencies=[Depends(get_current_user)])
def list_clients(q: str | None = Query(None, description="Search name or code"),
                 limit: int = Query(20, le=100), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db)) -> Page:
    repo = ClientRepository(db)
    items, total = repo.list(limit=limit, offset=offset, filters=repo.search_filters(q), order_by=Client.name)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{client_id}", response_model=ClientOut, dependencies=[Depends(get_current_user)])
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    client = ClientRepository(db).get(client_id)
    if client is None:
        raise NotFoundError("Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientOut, dependencies=[WRITE])
def update_client(client_id: uuid.UUID, body: ClientUpdate, db: Session = Depends(get_db)) -> Client:
    repo = ClientRepository(db)
    client = repo.get(client_id)
    if client is None:
        raise NotFoundError("Client not found")
    return repo.update(client, body.model_dump(exclude_unset=True))


@router.delete("/{client_id}", response_model=Message, dependencies=[Depends(require_roles(RoleName.ADMIN))])
def delete_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Message:
    repo = ClientRepository(db)
    client = repo.get(client_id)
    if client is None:
        raise NotFoundError("Client not found")
    repo.delete(client)
    return Message(message="Client deleted")


@router.get("/{client_id}/portfolios", response_model=list[PortfolioOut], dependencies=[Depends(get_current_user)])
def client_portfolios(client_id: uuid.UUID, db: Session = Depends(get_db)):
    if ClientRepository(db).get(client_id) is None:
        raise NotFoundError("Client not found")
    return PortfolioRepository(db).for_client(client_id)
