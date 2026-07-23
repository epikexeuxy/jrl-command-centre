# Build log — Phase 1 (22 Jul 2026)

Verified state at delivery:

- `pytest`: **21 passed** — XIRR matches the Excel fixture (0.373362), TWR is
  flow-immune, beta of a 2× levered series = 2.0, MDD on a known path = −50%,
  full API flow (CSV reject/commit, overview AUM exact, XIRR/TWR > 0, RBAC 403).
- Live smoke against MFAPI.in: login → overview (AUM ₹35.2 L, live NAVs for
  122639 / 118989 / 120186) → performance (401-pt series + NIFTY benchmark,
  flow-adjusted abs 0.77% / XIRR 0.74% with `static_share_pct:88.0` explaining
  PE damping) → risk (vol, Sharpe, VaR, beta/alpha, 371 rolling points) →
  correlation (3×3) → WeasyPrint PDF rendered and visually checked.
- Migration `7e5e7da2ccb9` creates all 15 tables; CI re-applies it on PostgreSQL.
- Frontend production build compiles (React 19 / Vite 8 / Tailwind v4).

Field notes for future maintainers:

- MFAPI quirks encountered and handled: transient 503s on `/mf`; renamed funds
  ("HDFC Mid-Cap Opportunities" → "HDFC Mid Cap Fund", code 118989); merged
  funds keeping stale terminal NAVs (IDBI Nifty 50 → benchmark resolution now
  freshness-validates and prefers UTI 120716); hyphen/dot variants in scheme
  names (search normalises).
- email-validator rejects reserved TLDs (`.local`): strict EmailStr only on
  user creation; login/output accept stored strings.
- Value-based CAGR on a flowing portfolio is misleading — Performance
  intentionally reports TWR-based figures (see ARCHITECTURE.md).
