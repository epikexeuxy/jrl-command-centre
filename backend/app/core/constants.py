"""Shared enumerations. Stored as plain VARCHAR for cross-database portability."""
from enum import StrEnum


class RoleName(StrEnum):
    ADMIN = "admin"
    WEALTH_MANAGER = "wealth_manager"
    IB_ANALYST = "ib_analyst"
    VIEWER = "viewer"


class InstrumentType(StrEnum):
    MUTUAL_FUND = "MUTUAL_FUND"
    EQUITY = "EQUITY"
    BOND = "BOND"
    CASH = "CASH"
    REAL_ESTATE = "REAL_ESTATE"
    OTHER = "OTHER"


class AssetClass(StrEnum):
    EQUITY = "EQUITY"
    DEBT = "DEBT"
    HYBRID = "HYBRID"
    CASH = "CASH"
    ALTERNATIVES = "ALTERNATIVES"
    REAL_ESTATE = "REAL_ESTATE"


class PriceSource(StrEnum):
    MFAPI_LIVE = "MFAPI_LIVE"   # NAV pulled live from MFAPI.in by scheme code
    MANUAL = "MANUAL"           # mark-to-model: manually entered price (illiquid assets)
    COST = "COST"               # fallback: valued at average cost


class TxnType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    FEE = "FEE"


class DealStage(StrEnum):
    PROSPECTING = "PROSPECTING"
    MANDATE = "MANDATE"
    DUE_DILIGENCE = "DUE_DILIGENCE"
    NEGOTIATION = "NEGOTIATION"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"


class UploadKind(StrEnum):
    HOLDINGS_CSV = "HOLDINGS_CSV"
    TRANSACTIONS_CSV = "TRANSACTIONS_CSV"


class UploadStatus(StrEnum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
