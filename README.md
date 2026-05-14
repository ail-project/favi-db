# favi-db - a favicon-registry

A small Flask service that stores favicon metadata and hash values in a Redis-compatible backend.

The project is intentionally structured as a basis for a larger system:

- no original favicon file is persisted;
- hash-centric storage keyed by `sha256`;
- Redis set indexes for hash values, hosts, URLs, and tags;
- MurmurHash3 favicon hash support using the Shodan-style base64 convention;
- a companion CLI that discovers favicons, computes hashes locally, and submits metadata via the API.

## Layout

```text
app/
  __init__.py             Flask application factory
  api/routes.py           HTTP API
  redis_client.py         request-scoped Redis client
  services/hashing.py     favicon hash calculation
  services/store.py       Redis storage and indexes
tools/favicon_fetch.py    companion discovery/submission CLI
tests/                    pytest tests
```

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt

# Start Redis-compatible backend
redis-server

export REDIS_URL=redis://localhost:6379/0
export API_TOKEN=change-me
flask --app app.wsgi:app run --debug
```

## API

### Health

```bash
curl http://127.0.0.1:5000/api/v1/health
```

### Add favicon metadata

The recommended path is to calculate hashes on the client side and submit only metadata and hashes.

```bash
curl -X POST http://127.0.0.1:5000/api/v1/favicons \
  -H 'Authorization: Bearer change-me' \
  -H 'Content-Type: application/json' \
  -d '{
    "host": "example.org",
    "url": "https://example.org/favicon.ico",
    "hashes": {
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "sha1": "dummy",
      "md5": "dummy",
      "mmh3": "-123456789"
    },
    "metadata": {
      "content_type": "image/x-icon",
      "size": 1150,
      "http_status": 200
    },
    "tags": ["seed"]
  }'
```

For convenience during prototyping, the API also accepts `favicon_base64`. The server computes hashes and discards the bytes; it still does not persist the original file.

### Get by SHA-256

```bash
curl http://127.0.0.1:5000/api/v1/favicons/<sha256>
```

### Search

```bash
# Search by Shodan-style mmh3 favicon hash
curl 'http://127.0.0.1:5000/api/v1/search?algo=mmh3&value=-123456789'

# Search by alias
curl 'http://127.0.0.1:5000/api/v1/search?algo=murmur3&value=-123456789'

# Search by host
curl 'http://127.0.0.1:5000/api/v1/search?host=example.org'

# Search by tag
curl 'http://127.0.0.1:5000/api/v1/search?tag=seed'
```

## Companion CLI

```bash
python -m tools.favicon_fetch https://example.org \
  --api http://127.0.0.1:5000/api/v1 \
  --token change-me \
  --tag example \
  --first
```

Dry-run mode prints the payload without calling the API:

```bash
python -m tools.favicon_fetch https://example.org --dry-run --first
```

Optional brute-force discovery with a wordlist:

```bash
python -m tools.favicon_fetch https://example.org \
  --wordlist favicon-paths.txt \
  --api http://127.0.0.1:5000/api/v1 \
  --token change-me
```

## Redis data model

Canonical record:

```text
favicon:<sha256> -> JSON
```

Associated sets and indexes:

```text
favicons                          set of sha256 values
favicon:<sha256>:hosts            set of hosts where observed
favicon:<sha256>:urls             set of favicon URLs where observed
favicon:<sha256>:tags             set of labels
favicon:<sha256>:observations     capped list of last 100 observations
idx:hash:<algo>:<value>           set of sha256 values
idx:host:<host>                   set of sha256 values
idx:url:<sha256(url)>             set of sha256 values
idx:tag:<tag>                     set of sha256 values
url:<sha256(url)>                 original URL string for reverse lookup/debugging
```

## Notes for later expansion

Good next additions would be:

- stricter JSON schema validation;
- API pagination;
- authentication/authorization beyond one write token;
- enrichment jobs for TLS certificate, HTTP headers, screenshots, ASN, and passive DNS metadata;
- deduplication policies when multiple hosts share one favicon;
- background task queue for large scans;
- export endpoints for MISP objects or other threat-intel formats.
