from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, Response, current_app, jsonify, request

from app.redis_client import get_redis
from app.services.hashing import compute_hashes_from_base64
from app.services.store import FaviconStore
from app.api.openapi import build_openapi_spec

api_bp = Blueprint("api", __name__)


def require_token(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        expected = current_app.config.get("API_TOKEN")
        if not expected:
            return view(*args, **kwargs)

        header = request.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ").strip()
        if token != expected:
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)

    return wrapped


def store() -> FaviconStore:
    return FaviconStore(get_redis())


@api_bp.get("/health")
def api_health():
    redis = get_redis()
    redis.ping()
    return jsonify({"status": "ok", "backend": "valkey-compatible"})


@api_bp.get("/openapi.json")
def openapi_spec():
    return jsonify(build_openapi_spec())


@api_bp.get("/docs")
def swagger_ui():
    html = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>favi-db API docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: '/api/v1/openapi.json',
        dom_id: '#swagger-ui'
      });
    </script>
  </body>
</html>
"""
    return Response(html, mimetype="text/html")


@api_bp.post("/favicons")
@require_token
def add_favicon():
    payload = request.get_json(silent=True) or {}

    # Convenience path: callers may send a transient favicon_base64 value so the
    # API computes hashes and discards the bytes. The value is never persisted.
    if "favicon_base64" in payload:
        hashes = compute_hashes_from_base64(payload.pop("favicon_base64"))
        payload["hashes"] = hashes | dict(payload.get("hashes") or {})

    try:
        record = store().upsert(payload)
    except ValueError as exc:
        return jsonify({"error": "validation_error", "message": str(exc)}), 400
    return jsonify(record), 201


@api_bp.get("/favicons/<sha256>")
def get_favicon(sha256: str):
    record = store().get(sha256)
    if record is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(record)


@api_bp.get("/search")
def search():
    algo = request.args.get("algo")
    value = request.args.get("value") or request.args.get("hash")
    host = request.args.get("host")
    ip = request.args.get("ip")
    tag = request.args.get("tag")

    try:
        if algo and value:
            records = store().search_by_hash(algo, value)
        elif host:
            records = store().search_by_host(host)
        elif ip:
            records = store().search_by_ip(ip)
        elif tag:
            records = store().search_by_tag(tag)
        else:
            return jsonify(
                {
                    "error": "validation_error",
                    "message": "use ?algo=mmh3&value=... or ?host=... or ?ip=... or ?tag=...",
                }
            ), 400
    except ValueError as exc:
        return jsonify({"error": "validation_error", "message": str(exc)}), 400

    return jsonify({"count": len(records), "items": records})


@api_bp.get("/stats")
def stats():
    return jsonify(store().stats())
