from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.constants import AssetClass, InstrumentType, PriceSource, TxnType
from app.schemas.common import ORMModel


# ---------- Clients ----------
class ClientBase(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = None
    risk_profile: str | None = None
    relationship_manager_id: uuid.UUID | None = None
    notes: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    risk_profile: str | None = None
    relationship_manager_id: uuid.UUID | None = None
    notes: str | None = None


class ClientOut(ORMModel, ClientBase):
    id: uuid.UUID
    created_at: datetime


# ---------- Benchmarks ----------
class BenchmarkOut(ORMModel):
    id: uuid.UUID
    name: str
    mfapi_scheme_code: str | None
    description: str | None


# ---------- Portfolios ----------
class PortfolioBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_currency: str = "INR"
    inception_date: date | None = None
    benchmark_id: uuid.UUID | None = None


class PortfolioCreate(PortfolioBase):
    client_id: uuid.UUID


class PortfolioUpdate(BaseModel):
    name: str | None = None
    inception_date: date | None = None
    benchmark_id: uuid.UUID | None = None
    status: str | None = None


class PortfolioOut(ORMModel, PortfolioBase):
    id: uuid.UUID
    client_id: uuid.UUID
    status: str
    created_at: datetime


# ---------- Holdings ----------
class HoldingBase(BaseModel):
    instrument_type: InstrumentType
    identifier: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    units: Decimal = Field(gt=0)
    avg_cost: Decimal | None = Field(default=None, ge=0)
    asset_class: AssetClass | None = None
    sector: str | None = None
    geography: str | None = None
    price_source: PriceSource = PriceSource.MFAPI_LIVE
    manual_price: Decimal | None = Field(default=None, ge=0)
    manual_price_date: date | None = None

    @field_validator("price_source", mode="after")
    @classmethod
    def _validate_price_source(cls, v, info):
        itype = info.data.get("instrument_type")
        if itype and itype != InstrumentType.MUTUAL_FUND and v == PriceSource.MFAPI_LIVE:
            # Only mutual funds can be priced from MFAPI; others fall back to MANUAL/COST.
            return PriceSource.MANUAL if info.data.get("manual_price") is not None else PriceSource.COST
        return v


class HoldingCreate(HoldingBase):
    pass


class HoldingUpdate(BaseModel):
    name: str | None = None
    units: Decimal | None = Field(default=None, gt=0)
    avg_cost: Decimal | None = None
    asset_class: AssetClass | None = None
    sector: str | None = None
    geography: str | None = None
    price_source: PriceSource | None = None
    manual_price: Decimal | None = None
    manual_price_date: date | None = None


class HoldingOut(ORMModel):
    id: uuid.UUID
    portfolio_id: uuid.UUID
    instrument_type: str
    identifier: str
    name: str
    units: Decimal
    avg_cost: Decimal | None
    asset_class: str | None
    sector: str | None
    geography: str | None
    price_source: str
    manual_price: Decimal | None
    manual_price_date: date | None


# ---------- Transactions ----------
class TransactionBase(BaseModel):
    txn_type: TxnType
    txn_date: date
    identifier: str | None = None
    units: Decimal | None = Field(default=None, gt=0)
    price: Decimal | None = Field(default=None, ge=0)
    amount: Decimal = Field(gt=0, description="Positive money value; direction is implied by txn_type")
    description: str | None = None


class TransactionCreate(TransactionBase):
    holding_id: uuid.UUID | None = None


class TransactionOut(ORMModel, TransactionBase):
    id: uuid.UUID
    portfolio_id: uuid.UUID
    holding_id: uuid.UUID | None
