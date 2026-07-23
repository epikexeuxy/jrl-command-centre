from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.services.mfapi import get_mfapi_client

router = APIRouter(prefix="/market", tags=["market"], dependencies=[Depends(get_current_user)])


@router.get("/mf/search")
def search_schemes(q: str = Query(min_length=2), limit: int = Query(20, le=50)) -> list[dict]:
    return get_mfapi_client().search(q, limit=limit)


@router.get("/mf/{scheme_code}/latest")
def latest_nav(scheme_code: str) -> dict:
    meta, d, nav = get_mfapi_client().latest_nav(scheme_code)
    return {"meta": meta, "date": d.isoformat(), "nav": nav}


@router.get("/mf/{scheme_code}/nav")
def nav_history(scheme_code: str, days: int = Query(365, ge=1, le=3650)) -> dict:
    meta, rows = get_mfapi_client().nav_history(scheme_code)
    rows = rows[-days:]
    return {"meta": meta, "data": [{"date": d.isoformat(), "nav": n} for d, n in rows]}
