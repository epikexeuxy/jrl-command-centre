from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.constants import RoleName
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models import User
from app.repositories.repositories import PortfolioRepository
from app.services.analytics.engine import AnalyticsEngine
from app.services.pdf.report import generate_executive_summary

router = APIRouter(prefix="/portfolios/{portfolio_id}/reports", tags=["reports"])


@router.post("/executive-summary")
def executive_summary(portfolio_id: uuid.UUID,
                      user: User = Depends(require_roles(RoleName.ADMIN, RoleName.WEALTH_MANAGER)),
                      db: Session = Depends(get_db)) -> dict:
    portfolio = PortfolioRepository(db).get(portfolio_id)
    if portfolio is None:
        raise NotFoundError("Portfolio not found")
    engine = AnalyticsEngine(db)
    overview = engine.overview(portfolio_id)
    try:
        performance = engine.performance(portfolio_id)
    except Exception:
        performance = None
    try:
        risk = engine.risk(portfolio_id)
    except Exception:
        risk = None
    report = generate_executive_summary(db, portfolio, overview, performance, risk, generated_by_id=user.id)
    return {"report_id": str(report.id), "file": os.path.basename(report.file_path)}


@router.get("/{report_id}/download", dependencies=[Depends(get_current_user)])
def download(portfolio_id: uuid.UUID, report_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    from app.models import Report

    report = db.get(Report, report_id)
    if report is None or report.portfolio_id != portfolio_id or not os.path.exists(report.file_path):
        raise NotFoundError("Report not found")
    return FileResponse(report.file_path, media_type="application/pdf",
                        filename=os.path.basename(report.file_path))
