from __future__ import annotations

from flask import Flask, jsonify, redirect

from app.api.routes import api_bp
from app.config import Config
from app.redis_client import close_redis


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    app.teardown_appcontext(close_redis)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    @app.get("/")
    def index():
        return (
            """<!doctype html>
<html>
  <head><meta charset=\"utf-8\" /><title>favi-db</title></head>
  <body>
    <h1>favi-db</h1>
    <p>OpenAPI and Swagger documentation:</p>
    <ul>
      <li><a href=\"/docs\">Swagger UI</a></li>
      <li><a href=\"/openapi.json\">OpenAPI JSON</a></li>
    </ul>
  </body>
</html>""",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    @app.get("/docs")
    def swagger_docs_redirect():
        return redirect("/api/v1/docs", code=302)

    @app.get("/openapi.json")
    def openapi_redirect():
        return redirect("/api/v1/openapi.json", code=302)

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        return {"status": "ok"}, 200

    @app.errorhandler(404)
    def not_found(_: Exception):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(400)
    def bad_request(error: Exception):
        return jsonify({"error": "bad_request", "message": str(error)}), 400

    return app
