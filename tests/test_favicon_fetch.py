from types import SimpleNamespace

from tools import favicon_fetch


class DummyResponse(SimpleNamespace):
    pass


def _response(url: str) -> DummyResponse:
    return DummyResponse(
        url=url,
        content=b"ico",
        status_code=200,
        headers={"content-type": "image/x-icon"},
    )


def test_build_payload_omits_duplicate_favicon_host_ips(monkeypatch):
    monkeypatch.setattr(
        favicon_fetch,
        "resolve_host_ips",
        lambda host: {"ipv4": ["1.1.1.1"], "ipv6": ["::1"]},
    )

    payload = favicon_fetch.build_payload(
        "https://example.com",
        _response("https://example.com/favicon.ico"),
        html_title="Example",
        tags=[],
    )

    metadata = payload["metadata"]
    assert metadata["host_ipv4"] == ["1.1.1.1"]
    assert metadata["host_ipv6"] == ["::1"]
    assert "favicon_host_ipv4" not in metadata
    assert "favicon_host_ipv6" not in metadata


def test_build_payload_keeps_favicon_host_ips_for_different_host(monkeypatch):
    def _fake_resolver(host: str | None) -> dict[str, list[str]]:
        if host == "example.com":
            return {"ipv4": ["1.1.1.1"], "ipv6": []}
        return {"ipv4": ["2.2.2.2"], "ipv6": ["::2"]}

    monkeypatch.setattr(favicon_fetch, "resolve_host_ips", _fake_resolver)

    payload = favicon_fetch.build_payload(
        "https://example.com",
        _response("https://cdn.example.net/favicon.ico"),
        html_title="Example",
        tags=[],
    )

    metadata = payload["metadata"]
    assert metadata["favicon_host"] == "cdn.example.net"
    assert metadata["favicon_host_ipv4"] == ["2.2.2.2"]
    assert metadata["favicon_host_ipv6"] == ["::2"]
