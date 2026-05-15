import fakeredis
import pytest

from app import create_app
from app import redis_client


class TestConfig:
    TESTING = True
    API_TOKEN = "test-token"
    REDIS_URL = "redis://unused/0"
    JSON_SORT_KEYS = False


@pytest.fixture()
def client(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    app = create_app(TestConfig)

    def fake_get_redis():
        return fake

    monkeypatch.setattr(redis_client, "get_redis", fake_get_redis)
    # routes imported the function directly, so patch that reference too.
    import app.api.routes as routes

    monkeypatch.setattr(routes, "get_redis", fake_get_redis)

    with app.test_client() as test_client:
        yield test_client


def test_add_and_search_favicon(client):
    payload = {
        "host": "Example.Org",
        "url": "https://example.org/favicon.ico",
        "hashes": {
            "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "md5": "abc",
            "sha1": "def",
            "mmh3": "-123456789",
        },
        "metadata": {"size": 123, "content_type": "image/x-icon"},
        "tags": ["seed"],
    }
    response = client.post(
        "/api/v1/favicons",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 201
    assert response.json["hosts"] == ["example.org"]
    assert response.json["urls"] == ["https://example.org/favicon.ico"]

    by_hash = client.get("/api/v1/search?algo=murmur3&value=-123456789")
    assert by_hash.status_code == 200
    assert by_hash.json["count"] == 1

    by_host = client.get("/api/v1/search?host=example.org")
    assert by_host.status_code == 200
    assert by_host.json["count"] == 1


def test_search_by_ipv4_and_ipv6(client):
    payload_v4 = {
        "host": "203.0.113.10",
        "url": "https://203.0.113.10/favicon.ico",
        "hashes": {
            "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "mmh3": "111",
        },
    }
    payload_v6 = {
        "host": "2001:db8::1",
        "url": "https://[2001:db8::1]/favicon.ico",
        "hashes": {
            "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "mmh3": "222",
        },
    }

    for payload in (payload_v4, payload_v6):
        response = client.post(
            "/api/v1/favicons",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 201

    by_ipv4 = client.get("/api/v1/search?ip=203.0.113.10")
    assert by_ipv4.status_code == 200
    assert by_ipv4.json["count"] == 1
    assert by_ipv4.json["items"][0]["ips"] == ["203.0.113.10"]

    by_ipv6 = client.get("/api/v1/search?ip=2001:db8::1")
    assert by_ipv6.status_code == 200
    assert by_ipv6.json["count"] == 1
    assert by_ipv6.json["items"][0]["ips"] == ["2001:db8::1"]


def test_write_requires_token(client):
    response = client.post("/api/v1/favicons", json={})
    assert response.status_code == 401


def test_openapi_and_swagger_docs(client):
    spec = client.get("/api/v1/openapi.json")
    assert spec.status_code == 200
    assert spec.json["openapi"].startswith("3.")
    assert "/favicons" in spec.json["paths"]

    docs = client.get("/api/v1/docs")
    assert docs.status_code == 200
    assert "SwaggerUIBundle" in docs.get_data(as_text=True)

    root = client.get("/")
    assert root.status_code == 200
    assert "Swagger UI" in root.get_data(as_text=True)

    docs_redirect = client.get("/docs")
    assert docs_redirect.status_code == 302
    assert docs_redirect.headers["Location"].endswith("/api/v1/docs")

    openapi_redirect = client.get("/openapi.json")
    assert openapi_redirect.status_code == 302
    assert openapi_redirect.headers["Location"].endswith("/api/v1/openapi.json")
