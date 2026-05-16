from __future__ import annotations

import hashlib
import ipaddress
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


def normalize_ip(ip: str) -> str:
    candidate = ip.strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError as exc:
        raise ValueError("ip must be a valid IPv4 or IPv6 address") from exc


def extract_ip(host: str) -> str | None:
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None

from redis import Redis

HASH_ALIASES = {
    "murmur3": "mmh3",
    "mmh3_32": "mmh3",
    "shodan": "mmh3",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_host(host: str | None, url: str | None) -> str:
    if host:
        return host.strip().lower().rstrip(".")
    if url:
        parsed = urlparse(url)
        if parsed.hostname:
            return parsed.hostname.lower().rstrip(".")
    raise ValueError("host is required when it cannot be inferred from url")


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("url must be absolute, e.g. https://example.org/favicon.ico")
    return parsed.geturl()


def url_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def canonical_algo(algo: str) -> str:
    return HASH_ALIASES.get(algo.strip().lower(), algo.strip().lower())


class FaviconStore:
    """Valkey-compatible store for favicon hash records and search indexes."""

    def __init__(self, redis: Redis):
        self.redis = redis

    def upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        hashes = dict(payload.get("hashes") or {})
        if not hashes.get("sha256"):
            raise ValueError("hashes.sha256 is required")

        sha256 = str(hashes["sha256"]).lower()
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise ValueError("hashes.sha256 must be a 64-character hexadecimal string")
        hashes["sha256"] = sha256

        url = normalize_url(str(payload.get("url", "")))
        host = normalize_host(payload.get("host"), url)
        now = utc_now()
        key = f"favicon:{sha256}"

        previous_raw = self.redis.get(key)
        previous = json.loads(previous_raw) if previous_raw else {}

        metadata = previous.get("metadata", {}) | dict(payload.get("metadata") or {})
        record = {
            "sha256": sha256,
            "hashes": previous.get("hashes", {}) | hashes,
            "metadata": metadata,
            "first_seen": previous.get("first_seen", payload.get("first_seen") or now),
            "last_seen": payload.get("last_seen") or now,
        }

        observation = {
            "host": host,
            "url": url,
            "seen_at": payload.get("seen_at") or now,
            "source": payload.get("source") or "api",
            "metadata": payload.get("metadata") or {},
        }

        tags = {str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()}

        pipe = self.redis.pipeline(transaction=True)
        pipe.set(key, json.dumps(record, sort_keys=True))
        pipe.sadd("favicons", sha256)
        pipe.sadd(f"favicon:{sha256}:hosts", host)
        pipe.sadd(f"favicon:{sha256}:urls", url)
        pipe.sadd(f"idx:host:{host}", sha256)

        if host_ip := extract_ip(host):
            pipe.sadd(f"favicon:{sha256}:ips", host_ip)
            pipe.sadd(f"idx:ip:{host_ip}", sha256)
        pipe.sadd(f"idx:url:{url_key(url)}", sha256)
        pipe.set(f"url:{url_key(url)}", url)
        observations_key = f"favicon:{sha256}:observations"
        latest_observation_raw = self.redis.lindex(observations_key, 0)
        latest_observation = json.loads(latest_observation_raw) if latest_observation_raw else None
        should_append_observation = not (
            latest_observation
            and latest_observation.get("host") == observation["host"]
            and latest_observation.get("url") == observation["url"]
        )

        if should_append_observation:
            pipe.lpush(observations_key, json.dumps(observation, sort_keys=True))
            pipe.ltrim(observations_key, 0, 99)

        for algo, value in record["hashes"].items():
            if value is None or value == "":
                continue
            pipe.sadd(f"idx:hash:{canonical_algo(algo)}:{value}", sha256)

        for tag in tags:
            pipe.sadd(f"favicon:{sha256}:tags", tag)
            pipe.sadd(f"idx:tag:{tag}", sha256)

        pipe.execute()
        return self.get(sha256) or record

    def get(self, sha256: str) -> dict[str, Any] | None:
        sha256 = sha256.lower()
        raw = self.redis.get(f"favicon:{sha256}")
        if not raw:
            return None
        record = json.loads(raw)
        record["hosts"] = sorted(self.redis.smembers(f"favicon:{sha256}:hosts"))
        record["urls"] = sorted(self.redis.smembers(f"favicon:{sha256}:urls"))
        record["tags"] = sorted(self.redis.smembers(f"favicon:{sha256}:tags"))
        record["ips"] = sorted(self.redis.smembers(f"favicon:{sha256}:ips"))
        observations = self.redis.lrange(f"favicon:{sha256}:observations", 0, 99)
        record["observations"] = [json.loads(item) for item in observations]
        return record



    def _search_index_paginated(self, index_key: str, *, offset: int, limit: int) -> tuple[int, list[dict[str, Any]]]:
        total = int(self.redis.scard(index_key))
        sha256_ids = self.redis.sort(index_key, start=offset, num=limit, alpha=True)
        items = [record for sha in sha256_ids if (record := self.get(sha))]
        return total, items
    def search_by_hash(self, algo: str, value: str, *, offset: int, limit: int) -> tuple[int, list[dict[str, Any]]]:
        algo = canonical_algo(algo)
        return self._search_index_paginated(f"idx:hash:{algo}:{value}", offset=offset, limit=limit)

    def search_by_host(self, host: str, *, offset: int, limit: int) -> tuple[int, list[dict[str, Any]]]:
        normalized = normalize_host(host, None)
        return self._search_index_paginated(f"idx:host:{normalized}", offset=offset, limit=limit)

    def search_by_ip(self, ip: str, *, offset: int, limit: int) -> tuple[int, list[dict[str, Any]]]:
        normalized = normalize_ip(ip)
        return self._search_index_paginated(f"idx:ip:{normalized}", offset=offset, limit=limit)

    def search_by_tag(self, tag: str, *, offset: int, limit: int) -> tuple[int, list[dict[str, Any]]]:
        return self._search_index_paginated(f"idx:tag:{tag}", offset=offset, limit=limit)

    def stats(self) -> dict[str, int]:
        return {"favicons": int(self.redis.scard("favicons"))}
