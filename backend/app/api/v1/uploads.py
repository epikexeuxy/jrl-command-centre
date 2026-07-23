from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import get_settings
from app.core.constants import RoleName, UploadKind, UploadStatus
from app.core.exceptions import NotFoundError, ValidationFailure
from app.db.session import get_db
from app.models import Portfolio, UploadedFile, User
from app.repositories.repositories import PortfolioRepository, UploadedFileRepository
from app.services import ingestion

router = APIRouter(prefix="/portfolios/{portfolio_id}/uploads", tags=["uploads"])

WRITE = require_roles(RoleName.ADMIN, RoleName.WEALTH_MANAGER)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _store(file: UploadFile, raw: bytes, kind: UploadKind, portfolio_id, user_id, db: Session) -> UploadedFile:
    settings = get_settings()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    stored = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}_{os.path.basename(file.filename or 'upload.csv')}")
    with open(stored, "wb") as fh:
        fh.write(raw)
    rec = UploadedFile(filename=file.filename or "upload.csv", stored_path=stored,
                       content_type=file.content_type, size_bytes=len(raw), kind=kind.value,
                       status=UploadStatus.PENDING.value, portfolio_id=portfolio_id, uploaded_by_id=user_id)
    return UploadedFileRepository(db).create(rec)


def _portfolio(db: Session, portfolio_id: uuid.UUID) -> Portfolio:
    p = PortfolioRepository(db).get(portfolio_id)
    if p is None:
        raise NotFoundError("Portfolio not found")
    return p


async def _read_csv_upload(file: UploadFile) -> bytes:
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValidationFailure("File exceeds the 5 MB upload limit")
    if not raw:
        raise ValidationFailure("Uploaded file is empty")
    return raw


@router.post("/holdings")
async def upload_holdings(portfolio_id: uuid.UUID,
                          file: UploadFile = File(...),
                          commit: bool = Query(False, description="false = validate only"),
                          user: User = Depends(WRITE),
                          db: Session = Depends(get_db)) -> dict:
    portfolio = _portfolio(db, portfolio_id)
    raw = await _read_csv_upload(file)
    record = _store(file, raw, UploadKind.HOLDINGS_CSV, portfolio_id, user.id, db)
    valid, errors = ingestion.validate_holdings_csv(raw)
    record.row_count = len(valid) + len(errors)
    record.error_report = errors or None
    if errors:
        record.status = UploadStatus.REJECTED.value
        return {"upload_id": str(record.id), "status": record.status,
                "valid_rows": len(valid), "errors": errors}
    if not commit:
        record.status = UploadStatus.VALIDATED.value
        return {"upload_id": str(record.id), "status": record.status,
                "valid_rows": len(valid), "errors": []}
    result = ingestion.commit_holdings(db, portfolio, valid)
    record.status = UploadStatus.COMMITTED.value
    return {"upload_id": str(record.id), "status": record.status, "valid_rows": len(valid),
            "errors": [], **result}


@router.post("/transactions")
async def upload_transactions(portfolio_id: uuid.UUID,
                              file: UploadFile = File(...),
                              commit: bool = Query(False),
                              user: User = Depends(WRITE),
                              db: Session = Depends(get_db)) -> dict:
    portfolio = _portfolio(db, portfolio_id)
    raw = await _read_csv_upload(file)
    record = _store(file, raw, UploadKind.TRANSACTIONS_CSV, portfolio_id, user.id, db)
    valid, errors = ingestion.validate_transactions_csv(raw)
    record.row_count = len(valid) + len(errors)
    record.error_report = errors or None
    if errors:
        record.status = UploadStatus.REJECTED.value
        return {"upload_id": str(record.id), "status": record.status,
                "valid_rows": len(valid), "errors": errors}
    if not commit:
        record.status = UploadStatus.VALIDATED.value
        return {"upload_id": str(record.id), "status": record.status,
                "valid_rows": len(valid), "errors": []}
    result = ingestion.commit_transactions(db, portfolio, valid)
    record.status = UploadStatus.COMMITTED.value
    return {"upload_id": str(record.id), "status": record.status, "valid_rows": len(valid),
            "errors": [], **result}
