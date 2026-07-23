"""WealthLens domain: clients, portfolios, holdings, transactions, benchmarks, uploads, reports."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import JSON, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Client(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "clients"

    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    risk_profile: Mapped[str | None] = mapped_column(String(30))  # CONSERVATIVE / BALANCED / AGGRESSIVE
    relationship_manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    relationship_manager = relationship("User", lazy="joined")
    portfolios: Mapped[list["Portfolio"]] = relationship(back_populates="client", cascade="all, delete-orphan")


class Benchmark(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "benchmarks"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mfapi_scheme_code: Mapped[str | None] = mapped_column(String(20))  # index-fund proxy on MFAPI.in
    description: Mapped[str | None] = mapped_column(String(500))


class Portfolio(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "portfolios"

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    inception_date: Mapped[date | None] = mapped_column(Date)
    benchmark_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("benchmarks.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    client: Mapped[Client] = relationship(back_populates="portfolios")
    benchmark: Mapped[Benchmark | None] = relationship(lazy="joined")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")


class Holding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "holdings"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_type: Mapped[str] = mapped_column(String(20), nullable=False)   # core.constants.InstrumentType
    # MFAPI scheme code / ticker / ISIN / free code
    identifier: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    units: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    avg_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))           # per-unit cost
    asset_class: Mapped[str | None] = mapped_column(String(20))                 # core.constants.AssetClass
    sector: Mapped[str | None] = mapped_column(String(100))
    geography: Mapped[str | None] = mapped_column(String(100))
    price_source: Mapped[str] = mapped_column(String(20), default="MFAPI_LIVE", nullable=False)
    manual_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))       # mark-to-model for illiquid assets
    manual_price_date: Mapped[date | None] = mapped_column(Date)
    extra: Mapped[dict | None] = mapped_column(JSON)

    portfolio: Mapped[Portfolio] = relationship(back_populates="holdings")


class Transaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "transactions"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    holding_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("holdings.id", ondelete="SET NULL"), index=True)
    # links CSV rows to holdings by instrument code
    identifier: Mapped[str | None] = mapped_column(String(64), index=True)
    txn_type: Mapped[str] = mapped_column(String(20), nullable=False)          # core.constants.TxnType
    txn_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    units: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    price: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    amount: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)    # positive money value of the transaction
    description: Mapped[str | None] = mapped_column(String(500))

    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")


class UploadedFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "uploaded_files"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)              # core.constants.UploadKind
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("portfolios.id", ondelete="SET NULL"), index=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    row_count: Mapped[int | None] = mapped_column(Integer)
    error_report: Mapped[list | None] = mapped_column(JSON)


class Report(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reports"

    portfolio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    # EXECUTIVE_SUMMARY / PORTFOLIO_SNAPSHOT / ...
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    params: Mapped[dict | None] = mapped_column(JSON)
