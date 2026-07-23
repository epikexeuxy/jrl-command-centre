from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.analytics import CorrelationResponse, PerformanceResponse, PortfolioOverview, RiskResponse
from app.services.analytics.engine import AnalyticsEngine

router = APIRouter(prefix="/portfolios/{portfolio_id}", tags=["analytics"],
                   dependencies=[Depends(get_current_user)])


@router.get("/overview", response_model=PortfolioOverview)
def overview(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> PortfolioOverview:
    return AnalyticsEngine(db).overview(portfolio_id)


@router.get("/performance", response_model=PerformanceResponse)
def performance(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> PerformanceResponse:
    return AnalyticsEngine(db).performance(portfolio_id)


@router.get("/risk", response_model=RiskResponse)
def risk(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> RiskResponse:
    return AnalyticsEngine(db).risk(portfolio_id)


@router.get("/correlation", response_model=CorrelationResponse)
def correlation(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> CorrelationResponse:
    return AnalyticsEngine(db).correlation(portfolio_id)
