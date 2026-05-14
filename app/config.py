from __future__ import annotations

import os


class Config:
    """Runtime configuration loaded from environment variables."""

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    API_TOKEN: str | None = os.getenv("API_TOKEN") or None
    JSON_SORT_KEYS: bool = False
