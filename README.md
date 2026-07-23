# JRL Command Centre

Internal platform for **J.R. Laddha Financial Services** with two modules:

| Module | Status | What it does |
|---|---|---|
| **WealthLens** | ✅ Phase 1 (this build) | HNI portfolio analytics: live MF NAVs (MFAPI.in/AMFI), XIRR, TWR, CAGR, volatility, Sharpe/Sortino, drawdown, VaR/CVaR, beta/alpha vs NIFTY 50, correlation, allocation, CSV ingestion, branded PDF executive summaries |
| **DealDesk** | 🔜 Phase 3 | IB pipeline CRM + AI-generated India Entry Briefs (Claude API) — schema already in place |

## Quickstart (Docker — recommended)

```bash
cp .env.example .env        # then edit SECRET_KEY + admin credentials
docker compose up --build -d
docker compose exec backend python -m app.db.seed
```

- Frontend: http://localhost:8080
- API + docs: http://localhost:8000/docs
- Default admin (change immediately): `admin@jrladdha.com` / `JrlAdmin@2026`

## Quickstart (local dev)

```bash
# Backend (Python 3.12)
cd backend
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.db.seed          # roles, admin, NIFTY benchmark, demo book (live NAVs)
uvicorn app.main:app --reload  # http://localhost:8000/docs

# Frontend (Node 22)
cd frontend
npm install
npm run dev                    # http://localhost:5173 (proxies /api -> :8000)
```

SQLite is the zero-config default locally; PostgreSQL in Docker/production.

## CSV formats

**Holdings** (`backend/data/samples/portfolio_holdings_sample.csv`)

```
instrument_type,identifier,name,units,avg_cost,asset_class,sector,geography,manual_price
MUTUAL_FUND,122639,Parag Parikh Flexi Cap...,1500,72.50,EQUITY,Diversified Equity,India,
OTHER,JRL-PE-001,Unlisted PE Stake,1,2500000,ALTERNATIVES,Private Equity,India,3100000
```

- `instrument_type`: `MUTUAL_FUND | STOCK | BOND | FD | OTHER`
- For `MUTUAL_FUND`, `identifier` is the **MFAPI/AMFI scheme code** (search via `GET /api/v1/market/mf/search?q=...`) and prices stream live.
- Anything else is valued at `manual_price` (else `avg_cost`) and flagged `static_valuation` in every response.

**Transactions** (`transactions_sample.csv`)

```
date,txn_type,identifier,units,price,amount,description
2025-07-22,BUY,122639,1050,68.20,71610.00,Initial allocation
```

- `txn_type`: `BUY | SELL | DEPOSIT | WITHDRAWAL | DIVIDEND | FEE`
- Rows auto-link to holdings by `identifier`.
- Upload with `?commit=false` first for a dry-run row-level error report; nothing commits unless the whole file is clean.

## Analytics semantics (important)

- **Overview → absolute return** = unrealised P&L vs invested cost (position view).
- **Performance → absolute/CAGR** = **flow-adjusted (TWR)**: deposits/withdrawals never masquerade as growth. XIRR is the money-weighted counterpart.
- Static-valued holdings damp portfolio series metrics; when they exceed 30% of AUM the API returns `static_share_pct:<x>` so the damping is explicit.
- Benchmark = NIFTY 50 proxied by UTI Nifty 50 Index Fund NAV (freshness-validated at seed time; stale merged funds are skipped).

## Environment

| Var | Default | Notes |
|---|---|---|
| `SECRET_KEY` | dev value | **Set a real one** (`openssl rand -hex 32`) |
| `DATABASE_URL` | `sqlite:///./jrl_dev.db` | Postgres in compose |
| `REDIS_URL` | empty | Optional; in-memory fallback |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@jrladdha.com` / `JrlAdmin@2026` | Seed bootstrap — rotate |
| `SEED_DEMO_DATA` | `true` | Demo client DEMO001 with live-NAV funds |
| `RISK_FREE_RATE` | `0.065` | Sharpe/Sortino/alpha |
| `ANTHROPIC_API_KEY` | empty | Needed only from Phase 3 (DealDesk AI briefs) |

## API surface (Phase 1)

Auth (`/auth/login|refresh|me`, JWT + roles: admin, wealth_manager, ib_analyst, viewer) ·
Users (admin) · Clients & Portfolios CRUD · Holdings & Transactions ·
CSV uploads with dry-run · Analytics (`/overview /performance /risk /correlation`) ·
Reports (PDF executive summary) · Market data (`/market/mf/*`). Interactive docs at `/docs`.

## Tests & CI

```bash
make test   # 21 tests: known-answer maths (XIRR vs Excel, TWR flow-immunity, beta=2, MDD) + full API flow
```

GitHub Actions runs ruff, applies migrations against real PostgreSQL, runs pytest, and builds the frontend.

## Roadmap

See `docs/PHASES.md` — Phase 2 (Monte Carlo, efficient frontier, alerts, report suite),
Phase 3 (DealDesk CRM + Claude-powered India Entry Briefs), Phase 4 (Celery jobs, e2e, deployment hardening).
