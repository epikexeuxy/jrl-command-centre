"""CSV ingestion: parse, row-level validation with a full error report, commit-if-clean.

Holdings CSV columns:
    instrument_type,identifier,name,units,avg_cost,asset_class,sector,geography[,manual_price]
Transactions CSV columns:
    date,txn_type,identifier,units,price,amount[,description]

Rules:
- Every row is validated through the same Pydantic models the JSON API uses.
- Nothing is committed unless the whole file is clean (all-or-nothing keeps the
  book consistent); the error report lists every failing row and reason.
- Holdings upserts match on (portfolio_id, identifier): existing rows are updated.
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationFailure
from app.models import Holding, Portfolio, Transaction
from app.repositories.repositories import HoldingRepository
from app.schemas.wealth import HoldingCreate, TransactionCreate

logger = logging.getLogger("app.ingestion")

HOLDINGS_REQUIRED = {"instrument_type", "identifier", "name", "units"}
TXN_REQUIRED = {"date", "txn_type", "amount"}
MAX_ROWS = 5000


def _read_csv(raw: bytes) -> list[dict[str, str]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationFailure("File is not valid UTF-8 text") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValidationFailure("CSV appears to be empty")
    rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]
    if not rows:
        raise ValidationFailure("CSV contains a header but no data rows")
    if len(rows) > MAX_ROWS:
        raise ValidationFailure(f"CSV exceeds the {MAX_ROWS}-row limit")
    return rows


def _clean(row: dict[str, str]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if v != ""}


def _fmt_errors(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())


def validate_holdings_csv(raw: bytes) -> tuple[list[HoldingCreate], list[dict]]:
    rows = _read_csv(raw)
    missing = HOLDINGS_REQUIRED - set(rows[0].keys())
    if missing:
        raise ValidationFailure(f"Missing required columns: {', '.join(sorted(missing))}")
    valid: list[HoldingCreate] = []
    errors: list[dict] = []
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            valid.append(HoldingCreate(**_clean(row)))
        except ValidationError as exc:
            errors.append({"row": i, "error": _fmt_errors(exc)})
    return valid, errors


def validate_transactions_csv(raw: bytes) -> tuple[list[TransactionCreate], list[dict]]:
    rows = _read_csv(raw)
    missing = TXN_REQUIRED - set(rows[0].keys())
    if missing:
        raise ValidationFailure(f"Missing required columns: {', '.join(sorted(missing))}")
    valid: list[TransactionCreate] = []
    errors: list[dict] = []
    for i, row in enumerate(rows, start=2):
        payload = _clean(row)
        if "date" in payload:
            payload["txn_date"] = payload.pop("date")
        try:
            valid.append(TransactionCreate(**payload))
        except ValidationError as exc:
            errors.append({"row": i, "error": _fmt_errors(exc)})
    return valid, errors


def commit_holdings(db: Session, portfolio: Portfolio, items: list[HoldingCreate]) -> dict:
    repo = HoldingRepository(db)
    created = updated = 0
    for item in items:
        data = item.model_dump()
        existing = repo.by_identifier(portfolio.id, item.identifier)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(Holding(portfolio_id=portfolio.id, **data))
            created += 1
    db.flush()
    return {"created": created, "updated": updated}


def commit_transactions(db: Session, portfolio: Portfolio, items: list[TransactionCreate]) -> dict:
    repo = HoldingRepository(db)
    created = linked = 0
    for item in items:
        data = item.model_dump()
        holding_id = data.pop("holding_id", None)
        if holding_id is None and item.identifier:
            h = repo.by_identifier(portfolio.id, item.identifier)
            if h is not None:
                holding_id = h.id
                linked += 1
        db.add(Transaction(portfolio_id=portfolio.id, holding_id=holding_id, **data))
        created += 1
    db.flush()
    return {"created": created, "auto_linked_to_holdings": linked}
