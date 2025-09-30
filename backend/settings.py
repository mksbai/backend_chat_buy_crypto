"""Application settings module."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    """Configuration values loaded from environment variables."""

    port: int
    cors_origins: str
    log_level: str
    delay_ms: int
    max_message_bytes: int

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        port=_env_int("PORT", 8000),
        cors_origins=_env_str("CORS_ORIGINS", "http://localhost:5173"),
        log_level=_env_str("LOG_LEVEL", "info"),
        delay_ms=_env_int("DELAY_MS", 80),
        max_message_bytes=_env_int("MAX_MESSAGE_BYTES", 10_240),
    )


settings = get_settings()
