"""Application settings.

Uses environment variables for configuration.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # Comma-separated origins; examples:
    # - http://localhost:3000
    # - https://your-app.vercel.app
    CORS_ORIGINS: str = ""
    PUBLIC_BASE_URL: str = ""

    # VAPID Keys for Push API
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "화홍고 학생회 건의함"
    SMTP_REPLY_TO_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    AUTO_CREATE_TABLES: bool = True


settings = Settings()
