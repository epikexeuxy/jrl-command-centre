"""Response shapes for the analytics endpoints."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class AllocationSlice(BaseModel):
    label: str
    value: float
    weight_pct: float


class HoldingValuation(BaseModel):
    holding_id: str
    name: str
    identifier: str
    instrument_type: str
    units: float
    price: float | None
    price_source: str
    price_date: date | None
    market_value: float
    invested_value: float | None
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None
    weight_pct: float


class PortfolioOverview(BaseModel):
    portfolio_id: str
    as_of: date
    aum: float
    invested: float | None
    absolute_return_pct: float | None
    holdings: list[HoldingValuation]
    allocation_by_asset_class: list[AllocationSlice]
    allocation_by_sector: list[AllocationSlice]
    allocation_by_geography: list[AllocationSlice]
    warnings: list[str]


class SeriesPoint(BaseModel):
    date: date
    value: float


class PeriodReturn(BaseModel):
    period: str
    return_pct: float


class PerformanceResponse(BaseModel):
    portfolio_id: str
    start_date: date
    end_date: date
    value_series: list[SeriesPoint]
    benchmark_series: list[SeriesPoint] | None   # rebased to portfolio start value
    daily_returns_tail: list[PeriodReturn]       # last 30 daily returns
    monthly_returns: list[PeriodReturn]
    yearly_returns: list[PeriodReturn]
    absolute_return_pct: float | None
    cagr_pct: float | None
    xirr_pct: float | None                       # money-weighted return
    twr_pct: float | None                        # time-weighted return (annualised)
    twr_cumulative_pct: float | None
    warnings: list[str]


class RiskResponse(BaseModel):
    portfolio_id: str
    start_date: date
    end_date: date
    volatility_pct: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown_pct: float | None
    calmar: float | None
    var_95_pct: float | None       # 1-day historical VaR, expressed as a positive loss %
    cvar_95_pct: float | None
    beta: float | None
    alpha_pct: float | None        # annualised Jensen's alpha vs benchmark
    information_ratio: float | None
    tracking_error_pct: float | None
    rolling_volatility: list[SeriesPoint]
    risk_free_rate_pct: float
    warnings: list[str]


class CorrelationResponse(BaseModel):
    portfolio_id: str
    labels: list[str]
    matrix: list[list[float | None]]
    warnings: list[str]
