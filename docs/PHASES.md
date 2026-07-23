# Delivery phases

## Phase 1 — Platform core + WealthLens analytics ✅ (this build)
Auth/RBAC, clients/portfolios/holdings/transactions, CSV ingestion with dry-run,
live MFAPI pricing, full analytics engine (XIRR/TWR/CAGR, vol, Sharpe, Sortino,
MDD, Calmar, VaR/CVaR, beta/alpha, TE/IR, rolling vol, correlation), branded PDF
executive summary, seed with freshness-validated NIFTY 50 benchmark, Docker,
CI, 21 tests.

## Phase 1b — WealthLens UI (next increment)
Login flow, client/portfolio dashboards, Recharts performance & drawdown charts,
allocation donuts, risk cards, correlation heatmap, CSV upload with error
review, report download. (Backend contract is frozen; UI consumes it.)

## Phase 2 — Advanced WealthLens
Monte Carlo goal projections, efficient frontier, rebalancing suggestions,
alerting (NAV moves, drawdown breaches), cash-sleeve model with internal
ledger, expanded report suite, scheduled report emails.

## Phase 3 — DealDesk
Kanban pipeline CRM (dnd-kit), companies/activities/tasks/notes, valuation
quick-models, and Claude-API "India Entry Brief" generator (needs
`ANTHROPIC_API_KEY`). Schema already migrated.

## Phase 4 — Hardening & scale
Celery/Redis background jobs (NAV refresh, report generation), e2e tests
(Playwright), observability, backup/restore runbook, production deployment.
