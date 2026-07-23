from fastapi import APIRouter

from app.api.v1 import analytics, auth, clients, health, market, portfolios, reports, uploads, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(clients.router)
api_router.include_router(portfolios.router)
api_router.include_router(analytics.router)
api_router.include_router(uploads.router)
api_router.include_router(reports.router)
api_router.include_router(market.router)
