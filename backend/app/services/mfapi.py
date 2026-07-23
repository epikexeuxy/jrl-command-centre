"""MFAPI.in client — live Indian mutual fund NAV data.

Verified response shapes (July 2026):
  GET /mf                -> [{"schemeCode": int, "schemeName": str, ...}]  (~38k schemes)
  GET /mf/{code}         -> {"meta": {...}, "data": [{"date": "dd-mm-yyyy", "nav": "..."}], "status": "SUCCESS"}
  GET /mf/{code}/latest  -> same shape, data has a single element

All calls are cached (Redis or in-memory) because the scheme list alone is ~10 MB.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

import httpx

from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, UpstreamError

logger = logging.getLogger("app.mfapi")


class MFAPIClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.MFAPI_BASE_URL.rstrip("/")
        self.nav_ttl = settings.MFAPI_CACHE_TTL_SECONDS
        self.list_ttl = settings.MFAPI_LIST_CACHE_TTL_SECONDS
        self._cache = get_cache()

    # ---------- HTTP ----------
    def _get(self, path: str, timeout: float = 30.0):
        url = f"{self.base_url}{path}"
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"MFAPI request failed: {exc}") from exc
        if resp.status_code == 404:
            raise NotFoundError("Scheme not found on MFAPI")
        if resp.status_code >= 400:
            raise UpstreamError(f"MFAPI returned HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as exc:
            raise UpstreamError("MFAPI returned invalid JSON") from exc

    # ---------- Scheme list & search ----------
    def list_schemes(self) -> list[dict]:
        cached = self._cache.get("mfapi:list")
        if cached is not None:
            return cached
        data = self._get("/mf", timeout=60.0)
        if not isinstance(data, list):
            raise UpstreamError("Unexpected MFAPI scheme list payload")
        slim = [{"schemeCode": d.get("schemeCode"), "schemeName": d.get("schemeName")} for d in data]
        self._cache.set("mfapi:list", slim, self.list_ttl)
        return slim

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(text.lower().replace("-", " ").replace(".", " ").split())

    def search(self, query: str, limit: int = 20) -> list[dict]:
        terms = [t for t in self._norm(query).split() if t]
        if not terms:
            return []
        results = []
        for s in self.list_schemes():
            name = self._norm(s.get("schemeName") or "")
            if all(t in name for t in terms):
                results.append(s)
                if len(results) >= limit:
                    break
        return results

    # ---------- NAV data ----------
    @staticmethod
    def _parse_history(payload: dict) -> tuple[dict, list[tuple[date, float]]]:
        meta = payload.get("meta") or {}
        rows: list[tuple[date, float]] = []
        for row in payload.get("data") or []:
            try:
                d = datetime.strptime(row["date"], "%d-%m-%Y").date()
                nav = float(row["nav"])
            except (KeyError, ValueError, TypeError):
                continue
            if nav > 0:
                rows.append((d, nav))
        rows.sort(key=lambda r: r[0])  # MFAPI returns newest-first; we want chronological
        return meta, rows

    def nav_history(self, scheme_code: str) -> tuple[dict, list[tuple[date, float]]]:
        key = f"mfapi:nav:{scheme_code}"
        cached = self._cache.get(key)
        if cached is not None:
            meta, rows = cached
            return meta, [(date.fromisoformat(d), n) for d, n in rows]
        payload = self._get(f"/mf/{scheme_code}")
        meta, rows = self._parse_history(payload)
        if not rows:
            raise NotFoundError(f"No NAV history available for scheme {scheme_code}")
        self._cache.set(key, (meta, [(d.isoformat(), n) for d, n in rows]), self.nav_ttl)
        return meta, rows

    def latest_nav(self, scheme_code: str) -> tuple[dict, date, float]:
        key = f"mfapi:latest:{scheme_code}"
        cached = self._cache.get(key)
        if cached is not None:
            meta, d, n = cached
            return meta, date.fromisoformat(d), n
        payload = self._get(f"/mf/{scheme_code}/latest")
        meta, rows = self._parse_history(payload)
        if not rows:
            raise NotFoundError(f"No latest NAV for scheme {scheme_code}")
        d, n = rows[-1]
        self._cache.set(key, (meta, d.isoformat(), n), min(self.nav_ttl, 3600))
        return meta, d, n


_client: MFAPIClient | None = None


def get_mfapi_client() -> MFAPIClient:
    global _client
    if _client is None:
        _client = MFAPIClient()
    return _client
