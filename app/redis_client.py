from __future__ import annotations

from flask import current_app, g
from redis import Redis


def get_redis() -> Redis:
    """Return a request-scoped backend client.

    The URL can point to Valkey, Kvrocks, Redis, DragonflyDB, or another
    Redis protocol compatible service.
    """

    if "redis" not in g:
        g.redis = Redis.from_url(
            current_app.config["REDIS_URL"],
            decode_responses=True,
            health_check_interval=30,
        )
    return g.redis


def close_redis(_: object | None = None) -> None:
    client = g.pop("redis", None)
    if client is not None:
        client.close()
