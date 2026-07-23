"""Risk mathematics. Pure functions over daily return arrays — no I/O.

All inputs are flow-adjusted daily simple returns (see returns.twr_daily_returns).
Annualisation uses trading-days scaling (default 252).
"""
from __future__ import annotations

import numpy as np

TRADING_DAYS = 252


def _clean(r: np.ndarray) -> np.ndarray:
    r = np.asarray(r, dtype=float)
    return r[np.isfinite(r)]


def annualised_volatility(daily_returns: np.ndarray, trading_days: int = TRADING_DAYS) -> float | None:
    r = _clean(daily_returns)
    if r.size < 5:
        return None
    return float(np.std(r, ddof=1) * np.sqrt(trading_days))


def annualised_mean_return(daily_returns: np.ndarray, trading_days: int = TRADING_DAYS) -> float | None:
    r = _clean(daily_returns)
    if r.size < 5:
        return None
    return float(np.mean(r) * trading_days)


def sharpe_ratio(daily_returns: np.ndarray, risk_free_rate: float, trading_days: int = TRADING_DAYS) -> float | None:
    vol = annualised_volatility(daily_returns, trading_days)
    mean = annualised_mean_return(daily_returns, trading_days)
    if vol is None or mean is None or vol == 0:
        return None
    return float((mean - risk_free_rate) / vol)


def sortino_ratio(daily_returns: np.ndarray, risk_free_rate: float, trading_days: int = TRADING_DAYS) -> float | None:
    """Downside deviation measured against the daily risk-free MAR."""
    r = _clean(daily_returns)
    if r.size < 5:
        return None
    mar_daily = risk_free_rate / trading_days
    downside = np.minimum(r - mar_daily, 0.0)
    downside_dev = np.sqrt(np.mean(downside**2)) * np.sqrt(trading_days)
    mean = float(np.mean(r) * trading_days)
    if downside_dev == 0:
        return None
    return float((mean - risk_free_rate) / downside_dev)


def max_drawdown(values: np.ndarray) -> float | None:
    """Maximum peak-to-trough decline of a value series, returned as a negative fraction."""
    v = _clean(values)
    if v.size < 2 or np.max(v) <= 0:
        return None
    running_peak = np.maximum.accumulate(v)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(running_peak > 0, v / running_peak - 1.0, 0.0)
    return float(np.min(dd))


def calmar_ratio(cagr_value: float | None, mdd: float | None) -> float | None:
    if cagr_value is None or mdd is None or mdd == 0:
        return None
    return float(cagr_value / abs(mdd))


def var_historical(daily_returns: np.ndarray, confidence: float = 0.95) -> float | None:
    """1-day historical VaR at `confidence`, returned as a POSITIVE loss fraction."""
    r = _clean(daily_returns)
    if r.size < 20:
        return None
    q = np.percentile(r, (1.0 - confidence) * 100.0)
    return float(max(0.0, -q))


def cvar_historical(daily_returns: np.ndarray, confidence: float = 0.95) -> float | None:
    """Expected shortfall beyond the VaR threshold, as a POSITIVE loss fraction."""
    r = _clean(daily_returns)
    if r.size < 20:
        return None
    q = np.percentile(r, (1.0 - confidence) * 100.0)
    tail = r[r <= q]
    if tail.size == 0:
        return None
    return float(max(0.0, -np.mean(tail)))


def beta_alpha(portfolio_returns: np.ndarray, benchmark_returns: np.ndarray,
               risk_free_rate: float, trading_days: int = TRADING_DAYS) -> tuple[float | None, float | None]:
    """CAPM beta and annualised Jensen's alpha vs the benchmark (paired daily returns)."""
    rp, rb = np.asarray(portfolio_returns, float), np.asarray(benchmark_returns, float)
    mask = np.isfinite(rp) & np.isfinite(rb)
    rp, rb = rp[mask], rb[mask]
    if rp.size < 20:
        return None, None
    var_b = np.var(rb, ddof=1)
    if var_b == 0:
        return None, None
    beta = float(np.cov(rp, rb, ddof=1)[0, 1] / var_b)
    rp_ann = float(np.mean(rp) * trading_days)
    rb_ann = float(np.mean(rb) * trading_days)
    alpha = (rp_ann - risk_free_rate) - beta * (rb_ann - risk_free_rate)
    return beta, float(alpha)


def information_ratio(portfolio_returns: np.ndarray, benchmark_returns: np.ndarray,
                      trading_days: int = TRADING_DAYS) -> tuple[float | None, float | None]:
    """(information_ratio, annualised tracking error) from paired daily returns."""
    rp, rb = np.asarray(portfolio_returns, float), np.asarray(benchmark_returns, float)
    mask = np.isfinite(rp) & np.isfinite(rb)
    active = rp[mask] - rb[mask]
    if active.size < 20:
        return None, None
    te_daily = np.std(active, ddof=1)
    if te_daily == 0:
        return None, None
    ir = float(np.mean(active) / te_daily * np.sqrt(trading_days))
    return ir, float(te_daily * np.sqrt(trading_days))


def rolling_volatility(daily_returns: np.ndarray, window: int = 30,
                       trading_days: int = TRADING_DAYS) -> np.ndarray:
    """Annualised rolling volatility; positions before `window` observations are NaN."""
    r = np.asarray(daily_returns, dtype=float)
    out = np.full(r.shape, np.nan)
    if r.size < window:
        return out
    for i in range(window - 1, r.size):
        seg = r[i - window + 1 : i + 1]
        seg = seg[np.isfinite(seg)]
        if seg.size >= max(5, window // 2):
            out[i] = np.std(seg, ddof=1) * np.sqrt(trading_days)
    return out


def correlation_matrix(return_columns: dict[str, np.ndarray]) -> tuple[list[str], np.ndarray]:
    """Pairwise correlation across labelled daily-return series (pairwise-complete)."""
    labels = list(return_columns.keys())
    n = len(labels)
    mat = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(i, n):
            a = np.asarray(return_columns[labels[i]], float)
            b = np.asarray(return_columns[labels[j]], float)
            mask = np.isfinite(a) & np.isfinite(b)
            if mask.sum() >= 20 and np.std(a[mask]) > 0 and np.std(b[mask]) > 0:
                c = float(np.corrcoef(a[mask], b[mask])[0, 1])
            else:
                c = np.nan
            mat[i, j] = mat[j, i] = c
    return labels, mat
