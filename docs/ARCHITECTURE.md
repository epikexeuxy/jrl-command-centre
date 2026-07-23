# Architecture

```
frontend (React 19 + Vite + Tailwind v4)
   │  /api proxy (dev) · nginx (prod)
   ▼
FastAPI app (app/main.py)
   ├─ api/v1/*        thin routers: validation, RBAC, serialization
   ├─ services/       domain logic
   │    ├─ mfapi.py            cached MFAPI.in client (list/search/history, 503-tolerant)
   │    ├─ ingestion.py        CSV validate → all-or-nothing commit
   │    ├─ analytics/          returns.py · risk.py · timeseries.py · engine.py
   │    └─ pdf/                WeasyPrint executive summary (Jinja2 template)
   ├─ repositories/   SQLAlchemy 2.0 typed queries
   ├─ models/         15 tables (WealthLens + DealDesk schema, users/roles)
   └─ core/           settings · JWT/bcrypt · errors · logging · cache · rate limits
        │
        ├─ PostgreSQL (prod) / SQLite (dev) via Alembic migrations
        ├─ Redis (optional) — MFAPI cache + rate-limit storage, in-memory fallback
        └─ MFAPI.in — live AMFI NAVs
```

## Analytics pipeline

1. **timeseries.build_portfolio_series** replays transactions into daily unit
   ledgers, prices MF holdings on forward-filled MFAPI NAV history, values
   static holdings at manual mark/cost (flagged), and emits `(dates, values,
   flows, warnings)` with `static_share_pct` when flat-priced assets ≥30% of AUM.
2. **returns.py** — XIRR (Newton with bisection fallback), TWR daily returns
   `r_t=(V_t−F_t)/V_{t−1}−1`, compounding, ACT/365 annualisation, period tables
   compounded from daily returns (flow-immune).
3. **risk.py** — annualised vol, Sharpe, Sortino, max drawdown, Calmar,
   historical VaR/CVaR (positive-loss convention), OLS beta/alpha vs benchmark,
   tracking error, information ratio, rolling vol, pairwise correlation (≥20 obs).
4. **engine.py** orchestrates per endpoint and downsamples chart series.

## Decisions

- **Flow-adjusted headline metrics** — raw V_end/V_start "returns" count deposits
  as growth; Performance abs/CAGR therefore report TWR. XIRR gives the
  money-weighted view. Overview keeps position P&L (invested vs market).
- **Sync SQLAlchemy** in FastAPI threadpool: simpler, plenty for internal scale.
- **Server-rendered PDF** (WeasyPrint) so reports are headless-safe and brandable.
- **Full schema now, phased routers** — DealDesk tables exist from day one so
  Phase 3 is additive, no migration churn.
- **Graceful market-data degradation** — MFAPI 503s log warnings; analytics fall
  back to last known series rather than failing the request.

## Security

JWT access (30 min) + refresh (14 d), bcrypt hashing, role checks per route
group, login rate-limited 5/min/IP, strict-email validation only on user
creation, uniform JSON error envelope, request-id logging middleware.
