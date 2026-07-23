"""End-to-end WealthLens flow on the API: client -> portfolio -> CSV uploads -> analytics.

MFAPI is monkeypatched with a deterministic synthetic NAV series so tests run
offline and produce stable numbers.
"""
from datetime import date, timedelta

import pytest

import app.services.mfapi as mfapi_module


class FakeMFAPI:
    """Deterministic linear NAV 100 -> 130 over the past 400 days."""

    def __init__(self):
        today = date.today()
        self.rows = [(today - timedelta(days=400 - i), 100.0 + i * 30.0 / 399.0) for i in range(400)]

    def latest_nav(self, code):
        d, n = self.rows[-1]
        return {"scheme_name": f"Fake Fund {code}"}, d, n

    def nav_history(self, code):
        return {"scheme_name": f"Fake Fund {code}"}, list(self.rows)

    def search(self, q, limit=20):
        return [{"schemeCode": 999001, "schemeName": "Fake Flexi Cap Direct Growth"}]


@pytest.fixture(autouse=True)
def fake_mfapi(monkeypatch):
    fake = FakeMFAPI()
    monkeypatch.setattr(mfapi_module, "_client", fake)
    yield fake


HOLDINGS_CSV = (
    "instrument_type,identifier,name,units,avg_cost,asset_class,sector,geography\n"
    "MUTUAL_FUND,999001,Fake Flexi Cap,100,105,EQUITY,Diversified,India\n"
    "OTHER,PE-1,Unlisted Stake,1,500000,ALTERNATIVES,PE,India\n"
)

BAD_HOLDINGS_CSV = (
    "instrument_type,identifier,name,units,avg_cost\n"
    "MUTUAL_FUND,999001,Fake Flexi Cap,-5,105\n"
)

TXNS_CSV_TEMPLATE = (
    "date,txn_type,identifier,units,price,amount,description\n"
    "{d1},BUY,999001,70,101,7070,initial\n"
    "{d2},BUY,999001,30,110,3300,top-up\n"
)


def _mk_book(client, admin_headers):
    c = client.post("/api/v1/clients", headers=admin_headers,
                    json={"code": "T-001", "name": "Test Client"})
    assert c.status_code == 201, c.text
    p = client.post("/api/v1/portfolios", headers=admin_headers,
                    json={"client_id": c.json()["id"], "name": "Test Portfolio",
                          "inception_date": (date.today() - timedelta(days=300)).isoformat()})
    assert p.status_code == 201, p.text
    return p.json()["id"]


def test_full_wealth_flow(client, admin_headers):
    pid = _mk_book(client, admin_headers)

    # Reject invalid CSV with a row-level error report
    r = client.post(f"/api/v1/portfolios/{pid}/uploads/holdings?commit=true",
                    headers=admin_headers,
                    files={"file": ("h.csv", BAD_HOLDINGS_CSV, "text/csv")})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED"
    assert r.json()["errors"][0]["row"] == 2

    # Commit valid holdings
    r = client.post(f"/api/v1/portfolios/{pid}/uploads/holdings?commit=true",
                    headers=admin_headers,
                    files={"file": ("h.csv", HOLDINGS_CSV, "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMMITTED" and r.json()["created"] == 2

    # Commit transactions (auto-linked to the MF holding by identifier)
    d1 = (date.today() - timedelta(days=250)).isoformat()
    d2 = (date.today() - timedelta(days=60)).isoformat()
    r = client.post(f"/api/v1/portfolios/{pid}/uploads/transactions?commit=true",
                    headers=admin_headers,
                    files={"file": ("t.csv", TXNS_CSV_TEMPLATE.format(d1=d1, d2=d2), "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["auto_linked_to_holdings"] == 2

    # Overview: AUM = 100 * 130 (fake NAV) + 500000 (manual/cost) and static warning present
    r = client.get(f"/api/v1/portfolios/{pid}/overview", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["aum"] == pytest.approx(100 * 130.0 + 500000.0, rel=1e-6)
    assert any(w.startswith("static_valuation:PE-1") for w in body["warnings"])
    weights = {h["identifier"]: h["weight_pct"] for h in body["holdings"]}
    assert weights["PE-1"] > weights["999001"]

    # Performance: linear NAV growth -> positive XIRR/TWR; units follow txn replay
    r = client.get(f"/api/v1/portfolios/{pid}/performance", headers=admin_headers)
    assert r.status_code == 200, r.text
    perf = r.json()
    assert perf["twr_cumulative_pct"] is not None and perf["twr_cumulative_pct"] > 0
    assert perf["xirr_pct"] is not None and perf["xirr_pct"] > 0
    assert len(perf["value_series"]) > 10

    # Risk: volatility of a linear (near-constant daily increment) series is tiny but finite
    r = client.get(f"/api/v1/portfolios/{pid}/risk", headers=admin_headers)
    assert r.status_code == 200, r.text
    risk = r.json()
    assert risk["max_drawdown_pct"] is not None
    assert risk["risk_free_rate_pct"] == pytest.approx(6.5)

    # Holdings list reflects the committed rows
    r = client.get(f"/api/v1/portfolios/{pid}/holdings", headers=admin_headers)
    assert {h["identifier"] for h in r.json()} == {"999001", "PE-1"}


def test_market_search_uses_service(client, admin_headers):
    r = client.get("/api/v1/market/mf/search?q=fake", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()[0]["schemeCode"] == 999001
