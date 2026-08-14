"""Application configuration loaded from environment variables.

Never hardcode secrets. All values can be overridden via environment
variables or a `.env` file at the repository root or in /backend.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    APP_NAME: str = "MessageFlow"
    APP_ENV: str = "development"  # development | production | test
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    # --- Database ---
    # Example: postgresql+psycopg2://messageflow:messageflow@localhost:5432/messageflow
    DATABASE_URL: str = "postgresql+psycopg2://messageflow:messageflow@localhost:5432/messageflow"

    # --- Security ---
    JWT_SECRET: str = "change-me-in-production-please-generate-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Validation ---
    # Default region used when a phone number has no international
    # prefix (e.g. "9876543210" -> +91 9876543210 when DEFAULT_REGION=IN).
    DEFAULT_REGION: str = "IN"

    # --- Uploads ---
    MAX_UPLOAD_MB: int = 10
    UPLOAD_DIR: str = "uploads"

    # --- Rate limiting ---
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_IMPORT: str = "10/minute"

    # --- Devices / pairing (Phase 2) ---
    # How long a pairing session stays valid (QR token).
    PAIRING_TOKEN_TTL_MINUTES: int = 5
    # How long a device JWT (WS auth) stays valid.
    DEVICE_TOKEN_EXPIRE_DAYS: int = 30
    # A device is marked OFFLINE when no heartbeat/WS traffic arrives
    # within this many seconds.
    DEVICE_OFFLINE_TIMEOUT_SECONDS: int = 60
    # Device WebSocket ping interval used to keep connections alive.
    DEVICE_WS_PING_SECONDS: int = 25

    # --- Sending (Phase 2) ---
    # Number of recipients dispatched per batch to the Android device.
    SEND_BATCH_SIZE: int = 5
    # Pacing: maximum messages dispatched per minute per device.
    # Conservative default; adjust to your carrier's acceptable policy.
    SEND_RATE_PER_MINUTE: int = 20
    # Enables the background dispatch loop (tests disable it).
    SEND_DISPATCH_ENABLED: bool = True
    # Automatic pause of the campaign when the paired device goes OFFLINE
    # during an active send job.
    PAUSE_CAMPAIGN_ON_DEVICE_OFFLINE: bool = True
    # Stop-keyword handling for inbound SMS forwarded by the device.
    STOP_KEYWORDS: str = "STOP,UNSUBSCRIBE,CANCEL,END,QUIT,STOPALL"
    # If true, a single confirmation reply is queued to the sender after a
    # STOP keyword is processed. Default OFF: never auto-reply.
    STOP_AUTO_REPLY_ENABLED: bool = False
    STOP_AUTO_REPLY_TEXT: str = "You have been unsubscribed from future messages."

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
