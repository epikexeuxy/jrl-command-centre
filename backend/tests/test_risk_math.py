"""Known-answer tests for the risk mathematics."""
import numpy as np
import pytest

from app.services.analytics import risk as K


def test_volatility_and_sharpe_deterministic():
    rng = np.random.default_rng(42)
    r = rng.normal(0.0005, 0.01, 500)
    vol = K.annualised_volatility(r, 252)
    assert vol == pytest.approx(np.std(r, ddof=1) * np.sqrt(252))
    sharpe = K.sharpe_ratio(r, risk_free_rate=0.065, trading_days=252)
    expected = (np.mean(r) * 252 - 0.065) / vol
    assert sharpe == pytest.approx(expected)


def test_max_drawdown_known_path():
    values = np.array([100, 120, 90, 95, 130, 65, 80], dtype=float)
    # Peak 130 -> trough 65 = -50%
    assert K.max_drawdown(values) == pytest.approx(-0.5)


def test_var_cvar_positive_loss_convention():
    r = np.concatenate([np.full(95, 0.001), np.full(5, -0.03)])
    var = K.var_historical(r, 0.95)
    cvar = K.cvar_historical(r, 0.95)
    assert var is not None and var >= 0
    assert cvar is not None and cvar >= var  # expected shortfall is at least VaR


def test_beta_of_leveraged_series_is_two():
    rng = np.random.default_rng(7)
    rb = rng.normal(0.0004, 0.01, 300)
    rp = 2.0 * rb  # exactly 2x the benchmark
    beta, alpha = K.beta_alpha(rp, rb, risk_free_rate=0.0, trading_days=252)
    assert beta == pytest.approx(2.0, abs=1e-9)
    assert alpha == pytest.approx(np.mean(rp) * 252 - 2.0 * np.mean(rb) * 252, abs=1e-9)


def test_correlation_matrix_perfect_pair():
    a = np.linspace(0.001, 0.01, 60)
    labels, mat = K.correlation_matrix({"A": a, "B": 2 * a, "C": -a})
    assert labels == ["A", "B", "C"]
    assert mat[0, 1] == pytest.approx(1.0)
    assert mat[0, 2] == pytest.approx(-1.0)
