from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.services.hashing import compute_hashes



def resolve_host_ips(host: str | None) -> dict[str, list[str]]:
    if not host:
        return {"ipv4": [], "ipv6": []}

    ipv4: set[str] = set()
    ipv6: set[str] = set()

    try:
        literal = ipaddress.ip_address(host)
        if literal.version == 4:
            ipv4.add(str(literal))
        else:
            ipv6.add(str(literal))
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            infos = []
        for family, *_rest in infos:
            sockaddr = _rest[-1]
            addr = sockaddr[0]
            if family == socket.AF_INET:
                ipv4.add(addr)
            elif family == socket.AF_INET6:
                ipv6.add(addr)

    return {"ipv4": sorted(ipv4), "ipv6": sorted(ipv6)}

DEFAULT_PATHS = [
    "/favicon.ico",
    "/favicon.png",
    "/favicon.svg",
    "/apple-touch-icon.png",
    "/apple-touch-icon-precomposed.png",
    "/assets/favicon.ico",
    "/static/favicon.ico",
]


def absolute_base(target: str) -> str:
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    parsed = urlparse(target)
    if not parsed.hostname:
        raise ValueError(f"invalid target URL: {target}")
    return f"{parsed.scheme}://{parsed.netloc}/"


def fetch(session: requests.Session, url: str, timeout: float, verify: bool) -> requests.Response | None:
    try:
        return session.get(url, timeout=timeout, verify=verify, allow_redirects=True)
    except requests.RequestException:
        return None


def discover_from_html(base_url: str, html: bytes) -> tuple[list[str], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel", [])).lower()
        href = link.get("href")
        if href and ("icon" in rel or "mask-icon" in rel):
            candidates.append(urljoin(base_url, href))

    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    return candidates, title


def candidate_urls(target: str, session: requests.Session, timeout: float, verify: bool) -> tuple[list[str], str | None]:
    base = absolute_base(target)
    candidates: list[str] = []
    title: str | None = None

    response = fetch(session, base, timeout, verify)
    if response and response.content:
        html_candidates, title = discover_from_html(base, response.content)
        candidates.extend(html_candidates)

    candidates.extend(urljoin(base, path) for path in DEFAULT_PATHS)

    seen = set()
    unique = []
    for url in candidates:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique, title


def wordlist_candidates(target: str, wordlist: Path) -> Iterable[str]:
    base = absolute_base(target)
    for raw in wordlist.read_text(encoding="utf-8", errors="ignore").splitlines():
        path = raw.strip()
        if not path or path.startswith("#"):
            continue
        yield urljoin(base, path.lstrip("/"))


def looks_like_favicon(response: requests.Response) -> bool:
    if response.status_code != 200 or not response.content:
        return False
    content_type = response.headers.get("content-type", "").lower()
    if content_type.startswith("image/"):
        return True
    # Many servers serve .ico as octet-stream or without a content type.
    return response.url.lower().endswith((".ico", ".png", ".svg", ".jpg", ".jpeg", ".webp"))


def build_payload(
    target: str,
    favicon_response: requests.Response,
    html_title: str | None,
    tags: list[str],
) -> dict:
    parsed_target = urlparse(absolute_base(target))
    parsed_icon = urlparse(favicon_response.url)
    content = favicon_response.content
    target_ip_info = resolve_host_ips(parsed_target.hostname)
    icon_ip_info = resolve_host_ips(parsed_icon.hostname)

    return {
        "host": parsed_target.hostname,
        "url": favicon_response.url,
        "hashes": compute_hashes(content).as_dict(),
        "metadata": {
            "size": len(content),
            "content_type": favicon_response.headers.get("content-type"),
            "http_status": favicon_response.status_code,
            "favicon_host": parsed_icon.hostname,
            "html_title": html_title,
            "host_ipv4": target_ip_info["ipv4"],
            "host_ipv6": target_ip_info["ipv6"],
            "favicon_host_ipv4": icon_ip_info["ipv4"],
            "favicon_host_ipv6": icon_ip_info["ipv6"],
        },
        "source": "favicon-fetch",
        "tags": tags,
    }


def post_payload(api_base: str, payload: dict, token: str | None, timeout: float) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.post(
        api_base.rstrip("/") + "/favicons",
        data=json.dumps(payload),
        headers=headers,
        timeout=timeout,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover a favicon, compute hashes, and submit metadata to the favicon API."
    )
    parser.add_argument("target", help="Base URL or hostname to inspect")
    parser.add_argument("--api", default="http://127.0.0.1:5000/api/v1", help="API base URL")
    parser.add_argument("--token", default=None, help="Bearer token for write access")
    parser.add_argument("--tag", action="append", default=[], help="Tag to add; can be repeated")
    parser.add_argument("--wordlist", type=Path, help="Optional path wordlist for brute-force discovery")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads instead of submitting")
    parser.add_argument("--first", action="store_true", help="Stop after the first accepted favicon")
    args = parser.parse_args(argv)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "favicon-fetch/0.1 (+https://example.invalid/favicon-registry)",
            "Accept": "text/html,application/xhtml+xml,image/*,*/*;q=0.8",
        }
    )

    verify = not args.insecure
    candidates, html_title = candidate_urls(args.target, session, args.timeout, verify)
    if args.wordlist:
        candidates.extend(wordlist_candidates(args.target, args.wordlist))

    submitted = 0
    seen_urls: set[str] = set()
    for url in candidates:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        response = fetch(session, url, args.timeout, verify)
        if response is None or not looks_like_favicon(response):
            continue

        payload = build_payload(args.target, response, html_title, args.tag)
        if args.dry_run:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            api_response = post_payload(args.api, payload, args.token, args.timeout)
            if api_response.status_code >= 400:
                print(
                    f"API error for {url}: {api_response.status_code} {api_response.text}",
                    file=sys.stderr,
                )
                continue
            print(json.dumps(api_response.json(), indent=2, sort_keys=True))
        submitted += 1
        if args.first:
            break

    if submitted == 0:
        print("No favicon found", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
