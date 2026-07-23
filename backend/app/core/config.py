"""Application configuration loaded from environment variables / .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "JRL Command Centre"
    APP_VERSION: str = "1.0.0-phase1"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Security ---
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # --- Database / cache ---
    DATABASE_URL: str = "sqlite:///./jrl_dev.db"
    REDIS_URL: str | None = None  # e.g. redis://redis:6379/0 ; falls back to in-memory cache

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080,http://localhost:3000"

    # --- Seed admin (used only by `python -m app.db.seed`) ---
    ADMIN_EMAIL: str = "admin@jrladdha.com"
    ADMIN_PASSWORD: str = "JrlAdmin@2026"
    SEED_DEMO_DATA: bool = True

    # --- Analytics ---
    RISK_FREE_RATE: float = 0.065        # annualised, Indian context default
    TRADING_DAYS_PER_YEAR: int = 252
    MFAPI_BASE_URL: str = "https://api.mfapi.in"
    MFAPI_CACHE_TTL_SECONDS: int = 6 * 3600
    MFAPI_LIST_CACHE_TTL_SECONDS: int = 24 * 3600

    # --- AI (DealDesk, Phase 3) ---
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # --- Files ---
    UPLOAD_DIR: str = "./var/uploads"
    REPORT_DIR: str = "./var/reports"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
