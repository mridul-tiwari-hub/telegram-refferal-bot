"""Application Configuration."""
import os
from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Bot credentials
    BOT_TOKEN: str = Field(default="8290140755:AAH8kBCR2uoc0E3dex1arF794Ax7kG4GzYU")
    ENVIRONMENT: Literal["development", "production", "test"] = "production"

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/bot.db",
        description="Async database connection string"
    )

    # Redis
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis connection URL for anti-spam and caching"
    )

    # Admin Logging
    ADMIN_LOG_CHAT_ID: Optional[int] = Field(
        default=None,
        description="Telegram Chat ID for moderation event logs"
    )

    @field_validator("ADMIN_LOG_CHAT_ID", "REDIS_URL", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    # Scheduler
    DEADLINE_CHECK_INTERVAL_SECONDS: int = Field(
        default=60,
        description="How often the background scheduler checks for expired referral requirements"
    )

    # Defaults
    DEFAULT_REFERRAL_DEADLINE_HOURS: int = Field(default=24)
    DEFAULT_REQUIRED_REFERRALS: int = Field(default=1)
    DEFAULT_FAILURE_ACTION: Literal["RESTRICT", "KICK", "NONE"] = "RESTRICT"
    DEFAULT_WARNING_LIMIT: int = Field(default=3)


settings = Settings()
