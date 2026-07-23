"""Return mathematics. Pure functions over (date, value) series and cashflows — no I/O.

Conventions
-----------
* Cashflow sign (investor perspective, for XIRR/MWR): money INTO the portfolio is
  negative (an outflow from the investor), money OUT is positive. The terminal
  portfolio value is appended as a positive flow.
* External flow F_t (for TWR): money INTO the portfolio at date t is positive.
  TWR sub-period return assumes flows land at the START of day t:
      r_t = (V_t - F_t) / V_{t-1} - 1
* Day count: ACT/365 for XIRR and CAGR.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np

DAYS_PER_YEAR = 365.0


# --------------------------------------------------------------------------- #
# Simple returns
# --------------------------------------------------------------------------- #
def absolute_return(start_value: float, end_value: float) -> float | None:
    if start_value is None or end_value is None or start_value <= 0:
        return None
    return end_value / start_value - 1.0


def cagr(start_value: float, end_value: float, start: date, end: date) -> float | None:
    """Compound annual growth rate. Returns None for spans under ~30 days (annualising
    a few days of movement produces meaningless triple-digit numbers)."""
    days = (end - start).days
    if start_value is None or end_value is None or start_value <= 0 or end_value <= 0 or days < 30:
        return None
    years = days / DAYS_PER_YEAR
    return (end_value / start_value) ** (1.0 / years) - 1.0


# --------------------------------------------------------------------------- #
# XIRR — money-weighted return on irregular cashflows
# --------------------------------------------------------------------------- #
def xirr(cashflows: list[tuple[date, float]]) -> float | None:
    """Iterative IRR on irregular cashflows (Newton-Raphson with bisection fallback).

    Requires at least one negative and one positive flow. Returns the annualised
    rate, or None when no solution exists in (-0.9999, 10].
    """
    flows = [(d, float(a)) for d, a in cashflows if a is not None and abs(float(a)) > 1e-12]
    if len(flows) < 2:
        return None
    amounts = [a for _, a in flows]
    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        return None

    t0 = min(d for d, _ in flows)
    times = np.array([(d - t0).days / DAYS_PER_YEAR for d, _ in flows])
    values = np.array([a for _, a in flows])

    def npv(rate: float) -> float:
        return float(np.sum(values / np.power(1.0 + rate, times)))

    def d_npv(rate: float) -> float:
        return float(np.sum(-times * values / np.power(1.0 + rate, times + 1.0)))

    # Newton-Raphson
    rate = 0.1
    for _ in range(100):
        f = npv(rate)
        if abs(f) < 1e-8:
            if -0.9999 < rate <= 10.0:
                return rate
            break
        df = d_npv(rate)
        if abs(df) < 1e-12:
            break
        step = f / df
        new_rate = rate - step
        if new_rate <= -0.9999:
            new_rate = (rate - 0.9999) / 2.0
        if abs(new_rate - rate) < 1e-10:
            rate = new_rate
            break
        rate = new_rate
    if abs(npv(rate)) < 1e-6 and -0.9999 < rate <= 10.0:
        return rate

    # Bisection fallback over a bracketing interval
    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-8:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


# --------------------------------------------------------------------------- #
# Time-weighted return
# --------------------------------------------------------------------------- #
def twr_daily_returns(values: np.ndarray, flows: np.ndarray) -> np.ndarray:
    """Flow-adjusted daily returns r_t = (V_t - F_t)/V_{t-1} - 1 for t >= 1.

    `values` and `flows` are aligned arrays over the same date grid; flows[t] is the
    net external money into the portfolio on day t (start-of-day convention).
    Days where V_{t-1} <= 0 produce a 0.0 return (guarded, not NaN).
    """
    if len(values) < 2:
        return np.array([])
    prev = values[:-1]
    curr = values[1:]
    f = flows[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(prev > 0, (curr - f) / prev - 1.0, 0.0)
    return np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)


def twr_cumulative(daily_returns: np.ndarray) -> float | None:
    if daily_returns.size == 0:
        return None
    return float(np.prod(1.0 + daily_returns) - 1.0)


def twr_annualised(daily_returns: np.ndarray, start: date, end: date) -> float | None:
    cum = twr_cumulative(daily_returns)
    days = (end - start).days
    if cum is None or days < 30 or (1.0 + cum) <= 0:
        return None
    return (1.0 + cum) ** (DAYS_PER_YEAR / days) - 1.0


# --------------------------------------------------------------------------- #
# Period aggregation
# --------------------------------------------------------------------------- #
def period_returns_from_values(dates: list[date], values: np.ndarray, freq: str) -> list[tuple[str, float]]:
    """Point-to-point returns per calendar month ('M') or year ('Y') from a value series.

    Note: these are value-based (not flow-adjusted) and are intended for the returns
    table display; flow-adjusted analytics use twr_daily_returns.
    """
    if len(dates) < 2:
        return []
    out: list[tuple[str, float]] = []
    def key(d: date) -> str:
        return f"{d.year}-{d.month:02d}" if freq == "M" else str(d.year)

    period_start_val = values[0]
    current = key(dates[0])
    last_val = values[0]
    for d, v in zip(dates[1:], values[1:]):
        k = key(d)
        if k != current:
            if period_start_val > 0:
                out.append((current, float(last_val / period_start_val - 1.0)))
            current = k
            period_start_val = last_val
        last_val = v
    if period_start_val > 0:
        out.append((current, float(last_val / period_start_val - 1.0)))
    return out


def period_returns_from_daily(dates: list[date], daily_returns, freq: str) -> list[tuple[str, float]]:
    """Compound flow-adjusted daily returns within each calendar month ('M') or year ('Y').

    `dates` aligns with `daily_returns` (i.e. dates[t] is the day of return r_t).
    Unlike value-based period returns, deposits/withdrawals do not distort these.
    """
    if len(dates) == 0:
        return []
    def key(d: date) -> str:
        return f"{d.year}-{d.month:02d}" if freq == "M" else str(d.year)
    out: list[tuple[str, float]] = []
    current = key(dates[0])
    acc = 1.0
    for d, r in zip(dates, daily_returns):
        k = key(d)
        if k != current:
            out.append((current, acc - 1.0))
            current, acc = k, 1.0
        acc *= (1.0 + float(r))
    out.append((current, acc - 1.0))
    return out


def is_finite(x: float | None) -> bool:
    return x is not None and math.isfinite(x)
