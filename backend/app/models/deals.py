"""DealDesk domain: companies, deals, activities, tasks, notes, AI reports.

The full schema is defined in Phase 1 so migrations stay stable; DealDesk API
routers and UI arrive in Phase 3.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import JSON, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sector: Mapped[str | None] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    revenue_cr: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))     # INR crore
    ebitda_cr: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    promoter_holding_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    extra: Mapped[dict | None] = mapped_column(JSON)

    deals: Mapped[list["Deal"]] = relationship(back_populates="company")


class Deal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deals"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="PROSPECTING", index=True)
    deal_type: Mapped[str | None] = mapped_column(String(50))   # M&A / FUNDRAISE / INDIA_ENTRY / ADVISORY
    sector: Mapped[str | None] = mapped_column(String(100))
    size_cr: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    probability_pct: Mapped[int | None] = mapped_column(Integer)
    next_action: Mapped[str | None] = mapped_column(String(255))
    next_action_date: Mapped[date | None] = mapped_column(Date)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # position inside a Kanban column

    company: Mapped[Company | None] = relationship(back_populates="deals", lazy="joined")
    activities: Mapped[list["Activity"]] = relationship(back_populates="deal", cascade="all, delete-orphan")
    tasks: Mapped[list["TaskItem"]] = relationship(back_populates="deal", cascade="all, delete-orphan")
    notes: Mapped[list["Note"]] = relationship(back_populates="deal", cascade="all, delete-orphan")


class Activity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "activities"

    deal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    # STAGE_CHANGE / NOTE / TASK / CALL / EMAIL / SYSTEM
    activity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    deal: Mapped[Deal] = relationship(back_populates="activities")


class TaskItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tasks"

    deal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)  # OPEN / DONE
    due_date: Mapped[date | None] = mapped_column(Date)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)

    deal: Mapped[Deal | None] = relationship(back_populates="tasks")


class Note(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notes"

    deal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    deal: Mapped[Deal | None] = relationship(back_populates="notes")


class AIReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_reports"

    deal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="INDIA_ENTRY_BRIEF")
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(100))
    output_md: Mapped[str | None] = mapped_column(Text)     # raw model output (markdown)
    # human-reviewed version — the only one shareable with clients
    edited_md: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)  # DRAFT / REVIEWED / EXPORTED
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
