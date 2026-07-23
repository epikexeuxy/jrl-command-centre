"""Idempotent seed: roles, admin user, benchmark, and (optionally) a demo book.

Run with:  python -m app.db.seed

Live behaviour: the benchmark and demo holdings are resolved against MFAPI.in at
seed time (scheme codes are looked up, latest NAVs pulled to backfill sensible
avg costs). Every network step degrades gracefully — a failed lookup logs a
warning and skips that item rather than aborting the seed.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import AssetClass, InstrumentType, PriceSource, RoleName, TxnType
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Benchmark, Client, Holding, Portfolio, Role, Transaction, User
from app.repositories.repositories import get_repositories
from app.services.mfapi import get_mfapi_client

logger = logging.getLogger("app.seed")

ROLE_DESCRIPTIONS = {
    RoleName.ADMIN: "Full access, user management",
    RoleName.WEALTH_MANAGER: "WealthLens read/write",
    RoleName.IB_ANALYST: "DealDesk read/write (Phase 3)",
    RoleName.VIEWER: "Read-only across modules",
}

# (search query, substrings that must NOT appear, units)
DEMO_FUNDS = [
    ("parag parikh flexi cap direct growth", (), 1500),
    ("hdfc mid cap fund growth option direct", ("large",), 800),
    ("icici prudential bluechip fund direct growth", ("us ",), 1200),
]


def seed_roles(db: Session) -> dict[str, Role]:
    repos = get_repositories(db)
    out: dict[str, Role] = {}
    for role_name in RoleName:
        role = repos["roles"].by_name(role_name.value)
        if role is None:
            role = repos["roles"].create(Role(name=role_name.value, description=ROLE_DESCRIPTIONS[role_name]))
            logger.info("Created role %s", role_name.value)
        out[role_name.value] = role
    return out


def seed_admin(db: Session, roles: dict[str, Role]) -> User:
    settings = get_settings()
    repos = get_repositories(db)
    admin = repos["users"].by_email(settings.ADMIN_EMAIL)
    if admin is None:
        admin = repos["users"].create(User(
            email=settings.ADMIN_EMAIL.lower(),
            full_name="JRL Administrator",
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            role_id=roles[RoleName.ADMIN.value].id,
        ))
        logger.info("Created admin user %s", settings.ADMIN_EMAIL)
    return admin


def seed_benchmark(db: Session) -> Benchmark | None:
    repos = get_repositories(db)
    existing, _ = repos["benchmarks"].list(limit=1, filters=[Benchmark.name == "NIFTY 50 (index fund proxy)"])
    if existing:
        return existing[0]
    scheme_code = None
    try:
        mf = get_mfapi_client()
        results = mf.search("nifty 50 index fund direct growth", limit=40)
        # Prefer UTI, then others; accept only schemes whose latest NAV is fresh
        # (merged/renamed funds keep stale terminal NAVs on MFAPI — e.g. IDBI post-merger).
        ranked = sorted(results, key=lambda r: 0 if "uti " in (r.get("schemeName") or "").lower() else 1)
        for cand in ranked:
            try:
                _, rows = mf.nav_history(str(cand["schemeCode"]))
            except Exception:
                continue
            if rows and (date.today() - rows[-1][0]).days <= 20:
                scheme_code = str(cand["schemeCode"])
                logger.info("Benchmark proxy resolved live: %s -> %s (last NAV %s)",
                            cand["schemeName"], scheme_code, rows[-1][0])
                break
        if scheme_code is None:
            logger.warning("No fresh NIFTY 50 index fund found; benchmark created without scheme code")
    except Exception:
        logger.warning("Could not resolve NIFTY index fund on MFAPI; benchmark created without scheme code",
                       exc_info=True)
    bench = repos["benchmarks"].create(Benchmark(
        name="NIFTY 50 (index fund proxy)",
        mfapi_scheme_code=scheme_code,
        description="NIFTY 50 TRI proxied by a NIFTY 50 index fund NAV from MFAPI.in",
    ))
    return bench


def seed_demo_book(db: Session, admin: User, benchmark: Benchmark | None) -> None:
    repos = get_repositories(db)
    if repos["clients"].by_code("DEMO001") is not None:
        logger.info("Demo book already present; skipping")
        return

    client = repos["clients"].create(Client(
        code="DEMO001", name="Demo Family Office", email="demo@jrl.local",
        risk_profile="BALANCED", relationship_manager_id=admin.id,
        notes="Seeded demonstration client. Safe to delete.",
    ))
    portfolio = repos["portfolios"].create(Portfolio(
        client_id=client.id, name="Core Equity MF Portfolio",
        inception_date=date.today() - timedelta(days=400),
        benchmark_id=benchmark.id if benchmark else None,
    ))

    mf = get_mfapi_client()
    buy_initial = date.today() - timedelta(days=365)
    buy_topup = date.today() - timedelta(days=120)

    for query, excludes, units in DEMO_FUNDS:
        try:
            results = mf.search(query, limit=10)
            results = [r for r in results
                       if not any(x in (r.get("schemeName") or "").lower() for x in excludes)]
            if not results:
                logger.warning("No MFAPI result for '%s'; skipping demo fund", query)
                continue
            scheme = results[0]
            code = str(scheme["schemeCode"])
            _, rows = mf.nav_history(code)
        except Exception:
            logger.warning("Live lookup failed for '%s'; skipping demo fund", query, exc_info=True)
            continue

        def nav_on(d: date) -> float:
            past = [n for dt, n in rows if dt <= d]
            return past[-1] if past else rows[0][1]

        nav_a, nav_b = nav_on(buy_initial), nav_on(buy_topup)
        units_a = int(units * 0.7)
        units_b = units - units_a
        avg_cost = (units_a * nav_a + units_b * nav_b) / units

        holding = Holding(
            portfolio_id=portfolio.id,
            instrument_type=InstrumentType.MUTUAL_FUND.value,
            identifier=code,
            name=scheme["schemeName"],
            units=Decimal(str(units)),
            avg_cost=Decimal(f"{avg_cost:.6f}"),
            asset_class=AssetClass.EQUITY.value,
            sector="Diversified Equity",
            geography="India",
            price_source=PriceSource.MFAPI_LIVE.value,
        )
        db.add(holding)
        db.flush()
        db.add_all([
            Transaction(portfolio_id=portfolio.id, holding_id=holding.id, identifier=code,
                        txn_type=TxnType.BUY.value, txn_date=buy_initial,
                        units=Decimal(str(units_a)), price=Decimal(f"{nav_a:.6f}"),
                        amount=Decimal(f"{units_a * nav_a:.2f}"), description="Seed: initial allocation"),
            Transaction(portfolio_id=portfolio.id, holding_id=holding.id, identifier=code,
                        txn_type=TxnType.BUY.value, txn_date=buy_topup,
                        units=Decimal(str(units_b)), price=Decimal(f"{nav_b:.6f}"),
                        amount=Decimal(f"{units_b * nav_b:.2f}"), description="Seed: top-up"),
        ])
        logger.info("Seeded holding %s: %s units", code, units)

    # One illiquid, manually marked asset to demonstrate mark-to-model valuation.
    db.add(Holding(
        portfolio_id=portfolio.id, instrument_type=InstrumentType.OTHER.value,
        identifier="JRL-PE-001", name="Unlisted PE Stake (mark-to-model)",
        units=Decimal("1"), avg_cost=Decimal("2500000"),
        asset_class=AssetClass.ALTERNATIVES.value, sector="Private Equity", geography="India",
        price_source=PriceSource.MANUAL.value, manual_price=Decimal("3100000"),
        manual_price_date=date.today() - timedelta(days=30),
    ))
    db.flush()
    logger.info("Demo book created: client DEMO001 / portfolio '%s'", portfolio.name)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    settings = get_settings()
    db = SessionLocal()
    try:
        roles = seed_roles(db)
        admin = seed_admin(db, roles)
        benchmark = seed_benchmark(db)
        if settings.SEED_DEMO_DATA:
            seed_demo_book(db, admin, benchmark)
        db.commit()
        logger.info("Seed complete. Admin login: %s", settings.ADMIN_EMAIL)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
