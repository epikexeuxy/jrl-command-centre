"""Analytics engine — orchestrates timeseries construction and the math layer
into the response payloads served by /portfolios/{id}/(overview|performance|risk|correlation).
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import InstrumentType, PriceSource
from app.core.exceptions import NotFoundError
from app.models import Holding, Portfolio, Transaction
from app.repositories.repositories import HoldingRepository, PortfolioRepository, TransactionRepository
from app.schemas.analytics import (
    AllocationSlice,
    CorrelationResponse,
    HoldingValuation,
    PerformanceResponse,
    PeriodReturn,
    PortfolioOverview,
    RiskResponse,
    SeriesPoint,
)
from app.services.analytics import returns as R
from app.services.analytics import risk as K
from app.services.analytics.timeseries import (
    build_benchmark_series,
    build_portfolio_series,
    xirr_cashflows,
)
from app.services.mfapi import get_mfapi_client

logger = logging.getLogger("app.analytics.engine")


def _f(x: Decimal | float | None) -> float | None:
    return None if x is None else float(x)


def _pct(x: float | None) -> float | None:
    return None if x is None or not np.isfinite(x) else round(x * 100.0, 4)


def _num(x: float | None) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x), 4)


class AnalyticsEngine:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    def _load(self, portfolio_id) -> tuple[Portfolio, list[Holding], list[Transaction]]:
        portfolio = PortfolioRepository(self.db).get(portfolio_id)
        if portfolio is None:
            raise NotFoundError("Portfolio not found")
        holdings = HoldingRepository(self.db).for_portfolio(portfolio_id)
        txns = TransactionRepository(self.db).for_portfolio(portfolio_id)
        return portfolio, holdings, txns

    # ------------------------------------------------------------------ #
    def overview(self, portfolio_id) -> PortfolioOverview:
        portfolio, holdings, _ = self._load(portfolio_id)
        warnings: list[str] = []
        valuations: list[HoldingValuation] = []
        mf = get_mfapi_client()

        for h in holdings:
            price: float | None = None
            price_date: date | None = None
            source = PriceSource(h.price_source)
            if InstrumentType(h.instrument_type) == InstrumentType.MUTUAL_FUND and source == PriceSource.MFAPI_LIVE:
                try:
                    _, price_date, price = mf.latest_nav(h.identifier)
                except Exception as exc:
                    warnings.append(f"live_nav_unavailable:{h.identifier} ({exc})")
            if price is None:
                price = _f(h.manual_price) if h.manual_price is not None else _f(h.avg_cost)
                price_date = h.manual_price_date
                if price is not None:
                    warnings.append(f"static_valuation:{h.identifier}:{h.name}")
            units = _f(h.units) or 0.0
            market_value = round(units * price, 2) if price is not None else 0.0
            invested = round(units * _f(h.avg_cost), 2) if h.avg_cost is not None else None
            pnl = round(market_value - invested, 2) if invested is not None else None
            pnl_pct = _pct(pnl / invested) if pnl is not None and invested else None
            valuations.append(HoldingValuation(
                holding_id=str(h.id), name=h.name, identifier=h.identifier,
                instrument_type=h.instrument_type, units=units, price=price,
                price_source=h.price_source, price_date=price_date,
                market_value=market_value, invested_value=invested,
                unrealized_pnl=pnl, unrealized_pnl_pct=pnl_pct, weight_pct=0.0,
            ))

        aum = round(sum(v.market_value for v in valuations), 2)
        for v in valuations:
            v.weight_pct = round(v.market_value / aum * 100.0, 2) if aum > 0 else 0.0

        invested_total = sum(v.invested_value for v in valuations if v.invested_value is not None)
        has_invested = any(v.invested_value is not None for v in valuations)

        def allocation(attr: str) -> list[AllocationSlice]:
            buckets: dict[str, float] = {}
            for h, v in zip(holdings, valuations):
                label = getattr(h, attr) or "Unclassified"
                buckets[label] = buckets.get(label, 0.0) + v.market_value
            return sorted(
                (AllocationSlice(label=k, value=round(val, 2),
                                 weight_pct=round(val / aum * 100.0, 2) if aum > 0 else 0.0)
                 for k, val in buckets.items()),
                key=lambda s: -s.value,
            )

        abs_ret = _pct(R.absolute_return(invested_total, aum)) if has_invested and invested_total > 0 else None
        return PortfolioOverview(
            portfolio_id=str(portfolio.id), as_of=date.today(), aum=aum,
            invested=round(invested_total, 2) if has_invested else None,
            absolute_return_pct=abs_ret,
            holdings=sorted(valuations, key=lambda v: -v.market_value),
            allocation_by_asset_class=allocation("asset_class"),
            allocation_by_sector=allocation("sector"),
            allocation_by_geography=allocation("geography"),
            warnings=warnings,
        )

    # ------------------------------------------------------------------ #
    def _series_bundle(self, portfolio_id):
        portfolio, holdings, txns = self._load(portfolio_id)
        series = build_portfolio_series(portfolio, holdings, txns)
        bench_values = None
        if series.dates and portfolio.benchmark and portfolio.benchmark.mfapi_scheme_code:
            bench_values = build_benchmark_series(portfolio.benchmark.mfapi_scheme_code, series.dates)
            if bench_values is None:
                series.warnings.append("benchmark_unavailable")
        return portfolio, holdings, txns, series, bench_values

    def performance(self, portfolio_id) -> PerformanceResponse:
        portfolio, _, txns, series, bench_values = self._series_bundle(portfolio_id)
        if not series.dates:
            raise NotFoundError("Not enough data to compute performance", )

        daily = R.twr_daily_returns(series.values, series.flows)
        twr_cum = R.twr_cumulative(daily)
        start, end = series.start, series.end

        bench_series_out = None
        if bench_values is not None and len(bench_values) == len(series.dates) and bench_values[0] > 0:
            rebased = bench_values / bench_values[0] * series.values[0]
            bench_series_out = [SeriesPoint(date=d, value=round(float(v), 2))
                                for d, v in zip(series.dates, rebased)]

        return_dates = series.dates[1:]
        monthly = R.period_returns_from_daily(return_dates, daily, "M")
        yearly = R.period_returns_from_daily(return_dates, daily, "Y")
        daily_tail = [PeriodReturn(period=d.isoformat(), return_pct=_pct(r) or 0.0)
                      for d, r in list(zip(series.dates[1:], daily))[-30:]]

        # Sample long series down for payload size (~max 400 points), always keeping the last point.
        step = max(1, len(series.dates) // 400)
        idx = list(range(0, len(series.dates), step))
        if idx[-1] != len(series.dates) - 1:
            idx.append(len(series.dates) - 1)
        value_series = [SeriesPoint(date=series.dates[i], value=round(float(series.values[i]), 2)) for i in idx]
        if bench_series_out is not None:
            bench_series_out = [bench_series_out[i] for i in idx]

        return PerformanceResponse(
            portfolio_id=str(portfolio.id), start_date=start, end_date=end,
            value_series=value_series, benchmark_series=bench_series_out,
            daily_returns_tail=daily_tail,
            monthly_returns=[PeriodReturn(period=p, return_pct=_pct(r) or 0.0) for p, r in monthly[-24:]],
            yearly_returns=[PeriodReturn(period=p, return_pct=_pct(r) or 0.0) for p, r in yearly],
            # Flow-adjusted: deposits/withdrawals must not read as growth.
            absolute_return_pct=_pct(twr_cum),
            cagr_pct=_pct(R.twr_annualised(daily, start, end)),
            xirr_pct=_pct(R.xirr(xirr_cashflows(series, txns))),
            twr_pct=_pct(R.twr_annualised(daily, start, end)),
            twr_cumulative_pct=_pct(twr_cum),
            warnings=series.warnings,
        )

    # ------------------------------------------------------------------ #
    def risk(self, portfolio_id) -> RiskResponse:
        portfolio, _, txns, series, bench_values = self._series_bundle(portfolio_id)
        if not series.dates:
            raise NotFoundError("Not enough data to compute risk metrics")

        rf = self.settings.RISK_FREE_RATE
        td = self.settings.TRADING_DAYS_PER_YEAR
        daily = R.twr_daily_returns(series.values, series.flows)
        # Restrict to days the portfolio actually moved OR either series traded — using the
        # full daily grid (weekends ffilled) would dilute volatility; drop exact-zero return days
        # only when they are calendar gaps for BOTH portfolio and benchmark.
        cagr_val = R.twr_annualised(daily, series.start, series.end)
        mdd = K.max_drawdown(series.values)

        beta = alpha = ir = te = None
        if bench_values is not None and len(bench_values) == len(series.values):
            bench_daily = np.diff(bench_values) / bench_values[:-1]
            moved = (np.abs(daily) > 1e-12) | (np.abs(bench_daily) > 1e-12)
            beta, alpha = K.beta_alpha(daily[moved], bench_daily[moved], rf, td)
            ir, te = K.information_ratio(daily[moved], bench_daily[moved], td)

        traded = np.abs(daily) > 1e-12
        daily_traded = daily[traded] if traded.sum() >= 20 else daily

        roll = K.rolling_volatility(daily, window=30, trading_days=td)
        roll_points = [SeriesPoint(date=d, value=round(float(v) * 100.0, 4))
                       for d, v in zip(series.dates[1:], roll) if np.isfinite(v)]
        step = max(1, len(roll_points) // 200)
        roll_points = roll_points[::step]

        return RiskResponse(
            portfolio_id=str(portfolio.id), start_date=series.start, end_date=series.end,
            volatility_pct=_pct(K.annualised_volatility(daily_traded, td)),
            sharpe=_num(K.sharpe_ratio(daily_traded, rf, td)),
            sortino=_num(K.sortino_ratio(daily_traded, rf, td)),
            max_drawdown_pct=_pct(mdd),
            calmar=_num(K.calmar_ratio(cagr_val, mdd)),
            var_95_pct=_pct(K.var_historical(daily_traded, 0.95)),
            cvar_95_pct=_pct(K.cvar_historical(daily_traded, 0.95)),
            beta=_num(beta), alpha_pct=_pct(alpha),
            information_ratio=_num(ir), tracking_error_pct=_pct(te),
            rolling_volatility=roll_points,
            risk_free_rate_pct=round(rf * 100.0, 2),
            warnings=series.warnings,
        )

    # ------------------------------------------------------------------ #
    def correlation(self, portfolio_id) -> CorrelationResponse:
        portfolio, _, _, series, _ = self._series_bundle(portfolio_id)
        if not series.dates:
            raise NotFoundError("Not enough data to compute correlations")
        columns: dict[str, np.ndarray] = {}
        for name, values in series.holding_values.items():
            v = np.asarray(values, float)
            if v.size < 21 or np.all(v <= 0):
                continue
            with np.errstate(divide="ignore", invalid="ignore"):
                r = np.where(v[:-1] > 0, v[1:] / v[:-1] - 1.0, np.nan)
            if np.nanstd(r) > 0:
                columns[name] = r
        if len(columns) < 2:
            return CorrelationResponse(portfolio_id=str(portfolio.id), labels=[], matrix=[],
                                       warnings=series.warnings + ["insufficient_series_for_correlation"])
        labels, mat = K.correlation_matrix(columns)
        matrix = [[(round(float(x), 4) if np.isfinite(x) else None) for x in row] for row in mat]
        return CorrelationResponse(portfolio_id=str(portfolio.id), labels=labels,
                                   matrix=matrix, warnings=series.warnings)
