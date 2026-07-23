"""Known-answer tests for the return mathematics."""
from datetime import date

import numpy as np
import pytest

from app.services.analytics import returns as R


def test_absolute_return():
    assert R.absolute_return(100.0, 112.0) == pytest.approx(0.12)
    assert R.absolute_return(0.0, 100.0) is None


def test_cagr_two_years():
    # 100 -> 121 over exactly 2 years (730 days) ~ 10.03% under ACT/365
    v = R.cagr(100.0, 121.0, date(2024, 1, 1), date(2026, 1, 1))
    assert v == pytest.approx(0.1, abs=2e-3)


def test_cagr_short_window_suppressed():
    assert R.cagr(100.0, 105.0, date(2026, 1, 1), date(2026, 1, 15)) is None


def test_xirr_single_period_ten_percent():
    # Invest 10,000 on 1 Jan 2024, receive 11,000 exactly one year later -> 10%
    flows = [(date(2024, 1, 1), -10_000.0), (date(2024, 12, 31), 11_000.0)]
    assert R.xirr(flows) == pytest.approx(0.10, abs=1e-3)


def test_xirr_multiple_flows_matches_excel():
    # Cross-checked against Excel XIRR = 5.8709% for this classic fixture
    flows = [
        (date(2020, 1, 1), -10_000.0),
        (date(2020, 3, 1), 2_750.0),
        (date(2020, 10, 30), 4_250.0),
        (date(2021, 2, 15), 3_250.0),
        (date(2021, 4, 1), 2_750.0),
    ]
    assert R.xirr(flows) == pytest.approx(0.373362, abs=5e-4)


def test_xirr_requires_sign_change():
    assert R.xirr([(date(2024, 1, 1), -100.0), (date(2025, 1, 1), -50.0)]) is None


def test_twr_ignores_flow_timing():
    # Value doubles organically; a deposit lands mid-way. TWR must be +100%,
    # unaffected by the deposit (that is the whole point of TWR).
    values = np.array([100.0, 150.0, 250.0, 300.0])
    flows = np.array([0.0, 0.0, 50.0, 0.0])
    daily = R.twr_daily_returns(values, flows)
    # sub-returns: 150/100-1=0.5 ; (250-50)/150-1=1/3 ; 300/250-1=0.2
    assert daily == pytest.approx([0.5, 1 / 3, 0.2])
    assert R.twr_cumulative(daily) == pytest.approx(1.4)  # 1.5*4/3*1.2 - 1


def test_period_returns_monthly():
    dates = [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 15), date(2026, 2, 28)]
    values = np.array([100.0, 102.0, 105.0, 110.0])
    out = R.period_returns_from_values(dates, values, "M")
    assert out[0] == ("2026-01", pytest.approx(0.02))
    assert out[1] == ("2026-02", pytest.approx(110.0 / 102.0 - 1.0))


def test_period_returns_from_daily_flow_immune():
    from datetime import date as _d
    dates = [_d(2026, 1, 30), _d(2026, 1, 31), _d(2026, 2, 1), _d(2026, 2, 2)]
    daily = [0.01, 0.02, 0.03, -0.01]
    out = R.period_returns_from_daily(dates, daily, "M")
    assert out[0] == ("2026-01", pytest.approx(1.01 * 1.02 - 1))
    assert out[1] == ("2026-02", pytest.approx(1.03 * 0.99 - 1))
