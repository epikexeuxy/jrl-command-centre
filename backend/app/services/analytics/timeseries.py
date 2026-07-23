"""Builds the daily portfolio value series and external-flow series.

Method
------
1. For every holding, derive a daily *units* series:
   - if the holding has BUY/SELL transactions, units follow the cumulative
     transaction quantity (step function);
   - otherwise units are treated as constant at the holding's current value
     (static book — common right after a CSV onboarding).
2. Price each holding daily:
   - MUTUAL_FUND with price_source=MFAPI_LIVE -> live NAV history from MFAPI.in,
     forward-filled across non-trading days;
   - anything else -> flat mark-to-model price (manual_price, else avg_cost).
     These contribute value but no return variance, and are surfaced in
     `static_valuation` warnings so the RM knows.
3. Sum across holdings on a shared daily calendar.
4. External flows F_t: +amount for BUY/DEPOSIT, -amount for SELL/WITHDRAWAL/
   DIVIDEND (dividends assumed paid out) — FEE reduces value like a withdrawal.

Assumption (documented for the Wealth team): buys are funded from outside the
portfolio and sale proceeds leave it — i.e. no internal cash ledger in Phase 1.
A cash-sleeve model is scheduled for Phase 2.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd

from app.core.constants import InstrumentType, PriceSource, TxnType
from app.models import Holding, Portfolio, Transaction
from app.services.mfapi import get_mfapi_client

logger = logging.getLogger("app.analytics.timeseries")

FLOW_SIGN = {
    TxnType.BUY: 1.0,
    TxnType.DEPOSIT: 1.0,
    TxnType.SELL: -1.0,
    TxnType.WITHDRAWAL: -1.0,
    TxnType.DIVIDEND: -1.0,
    TxnType.FEE: -1.0,
}

UNIT_SIGN = {TxnType.BUY: 1.0, TxnType.SELL: -1.0}


@dataclass
class PortfolioSeries:
    dates: list[date]
    values: np.ndarray                       # total portfolio value per day
    flows: np.ndarray                        # net external flow per day (start-of-day)
    holding_values: dict[str, np.ndarray]    # holding name -> daily value (for correlation)
    warnings: list[str] = field(default_factory=list)

    @property
    def start(self) -> date | None:
        return self.dates[0] if self.dates else None

    @property
    def end(self) -> date | None:
        return self.dates[-1] if self.dates else None


def _float(x: Decimal | float | None) -> float | None:
    return None if x is None else float(x)


def _units_series(index: pd.DatetimeIndex, holding: Holding, txns: list[Transaction]) -> pd.Series:
    """Daily units for one holding. Transaction replay when available, else constant."""
    relevant = [t for t in txns if t.units is not None and TxnType(t.txn_type) in UNIT_SIGN
                and (t.holding_id == holding.id or (t.identifier and t.identifier == holding.identifier))]
    if not relevant:
        return pd.Series(_float(holding.units) or 0.0, index=index)
    deltas = pd.Series(0.0, index=index)
    for t in relevant:
        ts = pd.Timestamp(t.txn_date)
        if ts < index[0]:
            deltas.iloc[0] += UNIT_SIGN[TxnType(t.txn_type)] * float(t.units)
        elif ts <= index[-1]:
            deltas.loc[ts] += UNIT_SIGN[TxnType(t.txn_type)] * float(t.units)
    units = deltas.cumsum().clip(lower=0.0)
    return units


def _price_series(index: pd.DatetimeIndex, holding: Holding, warnings: list[str]) -> pd.Series | None:
    itype = InstrumentType(holding.instrument_type)
    source = PriceSource(holding.price_source)
    if itype == InstrumentType.MUTUAL_FUND and source == PriceSource.MFAPI_LIVE:
        try:
            _, rows = get_mfapi_client().nav_history(holding.identifier)
        except Exception as exc:
            warnings.append(f"live_nav_unavailable:{holding.identifier}:{holding.name} ({exc})")
            return _flat_price(index, holding, warnings)
        nav = pd.Series({pd.Timestamp(d): n for d, n in rows}).sort_index()
        nav = nav.reindex(index.union(nav.index)).ffill().reindex(index)
        if nav.isna().all():
            warnings.append(f"nav_out_of_range:{holding.identifier}:{holding.name}")
            return None
        return nav
    return _flat_price(index, holding, warnings)


def _flat_price(index: pd.DatetimeIndex, holding: Holding, warnings: list[str]) -> pd.Series | None:
    price = _float(holding.manual_price)
    if price is None:
        price = _float(holding.avg_cost)
    if price is None:
        warnings.append(f"unpriceable:{holding.identifier}:{holding.name}")
        return None
    warnings.append(f"static_valuation:{holding.identifier}:{holding.name}")
    return pd.Series(price, index=index)


def build_portfolio_series(portfolio: Portfolio, holdings: list[Holding],
                           txns: list[Transaction], lookback_days: int = 3 * 365) -> PortfolioSeries:
    warnings: list[str] = []
    today = pd.Timestamp(date.today())

    # Series start: earliest transaction, else inception date, else the lookback window.
    candidates = [pd.Timestamp(t.txn_date) for t in txns]
    if portfolio.inception_date:
        candidates.append(pd.Timestamp(portfolio.inception_date))
    start = min(candidates) if candidates else today - pd.Timedelta(days=365)
    start = max(start, today - pd.Timedelta(days=lookback_days))
    if start >= today:
        start = today - pd.Timedelta(days=1)

    index = pd.date_range(start=start, end=today, freq="D")

    total = pd.Series(0.0, index=index)
    holding_values: dict[str, np.ndarray] = {}
    priced_any = False
    for h in holdings:
        price = _price_series(index, h, warnings)
        if price is None:
            continue
        units = _units_series(index, h, txns)
        value = (units * price).fillna(0.0)
        total = total.add(value, fill_value=0.0)
        holding_values[h.name] = value.to_numpy(dtype=float)
        priced_any = True

    if not priced_any:
        return PortfolioSeries(dates=[], values=np.array([]), flows=np.array([]),
                               holding_values={}, warnings=warnings + ["no_priceable_holdings"])

    # Trim leading zero-value days (before anything was held/priced).
    nz = np.nonzero(total.to_numpy() > 0)[0]
    if nz.size == 0:
        return PortfolioSeries(dates=[], values=np.array([]), flows=np.array([]),
                               holding_values={}, warnings=warnings + ["no_positive_values"])
    first = nz[0]
    index = index[first:]
    total = total.iloc[first:]
    holding_values = {k: v[first:] for k, v in holding_values.items()}

    # Flag how much of the terminal value sits in static (flat-priced) holdings —
    # a large share damps volatility/TWR and the RM should know why.
    static_names = {w.split(":", 2)[2] if w.count(":") >= 2 else ""
                    for w in warnings if w.startswith("static_valuation:")}
    terminal_total = float(total.iloc[-1])
    if terminal_total > 0 and static_names:
        static_val = sum(float(v[-1]) for k, v in holding_values.items() if k in static_names)
        share = static_val / terminal_total * 100.0
        if share >= 30.0:
            warnings.append(f"static_share_pct:{share:.1f}")

    flows = pd.Series(0.0, index=index)
    for t in txns:
        ts = pd.Timestamp(t.txn_date)
        if index[0] < ts <= index[-1]:  # flows on/before day 0 are embedded in the opening value
            flows.loc[ts] += FLOW_SIGN[TxnType(t.txn_type)] * float(t.amount)

    return PortfolioSeries(
        dates=[d.date() for d in index],
        values=total.to_numpy(dtype=float),
        flows=flows.to_numpy(dtype=float),
        holding_values=holding_values,
        warnings=warnings,
    )


def build_benchmark_series(scheme_code: str, dates: list[date]) -> np.ndarray | None:
    """Benchmark NAV forward-filled onto the portfolio's date grid."""
    try:
        _, rows = get_mfapi_client().nav_history(scheme_code)
    except Exception as exc:
        logger.warning("Benchmark NAV fetch failed for %s: %s", scheme_code, exc)
        return None
    nav = pd.Series({pd.Timestamp(d): n for d, n in rows}).sort_index()
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    aligned = nav.reindex(idx.union(nav.index)).ffill().reindex(idx)
    if aligned.isna().all():
        return None
    aligned = aligned.bfill()  # cover grid days that precede the first benchmark NAV
    return aligned.to_numpy(dtype=float)


def xirr_cashflows(series: PortfolioSeries, txns: list[Transaction]) -> list[tuple[date, float]]:
    """Investor-perspective cashflows for XIRR.

    Opening value counts as an initial investment (negative), in-window external
    flows carry the opposite sign of FLOW_SIGN (money in = investor outflow),
    and the terminal value closes the position (positive).
    """
    if not series.dates:
        return []
    flows: list[tuple[date, float]] = [(series.start, -float(series.values[0]))]
    for t in txns:
        if series.start < t.txn_date <= series.end:
            flows.append((t.txn_date, -FLOW_SIGN[TxnType(t.txn_type)] * float(t.amount)))
    flows.append((series.end, float(series.values[-1])))
    return flows
