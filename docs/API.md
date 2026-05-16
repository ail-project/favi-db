# favi-db API Reference

Base URL (local default): `http://127.0.0.1:5000/api/v1`

## Interactive Swagger / OpenAPI

- Swagger UI: `/api/v1/docs`
- OpenAPI JSON: `/api/v1/openapi.json`

## Authentication

Write operations require Bearer token auth when `API_TOKEN` is configured.

```bash
-H 'Authorization: Bearer change-me'
```

## Endpoints

### `GET /health`
Service health check.

```bash
curl http://127.0.0.1:5000/api/v1/health
```

### `POST /favicons`
Create or update a favicon record.

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

Convenience mode: include `favicon_base64` to let the server compute hashes. Bytes are discarded and never persisted.

### `GET /favicons/{sha256}`
Fetch a canonical record by SHA-256 key.

```bash
curl http://127.0.0.1:5000/api/v1/favicons/<sha256>
```

### `GET /search`
Search records by one selector, with pagination support (`limit` and `offset`):

- `?algo=<algo>&value=<hash>` (or `hash=` alias)
- `?host=<hostname>`
- `?tag=<tag>`

```bash
curl 'http://127.0.0.1:5000/api/v1/search?algo=mmh3&value=-123456789'
curl 'http://127.0.0.1:5000/api/v1/search?algo=murmur3&value=-123456789'
curl 'http://127.0.0.1:5000/api/v1/search?host=example.org'
curl 'http://127.0.0.1:5000/api/v1/search?tag=seed'
curl 'http://127.0.0.1:5000/api/v1/search?tag=seed&limit=25&offset=50'
```

Pagination fields in search responses:

- `count`: number of items in this page
- `total`: total number of matching records
- `limit`: requested page size
- `offset`: requested offset
- `has_more`: `true` if more records remain after this page

Validation rules:

- `limit` must be between `1` and `500`
- `offset` must be `0` or greater

### `GET /stats`
Returns backend aggregate counters and index cardinality summaries.

```bash
curl http://127.0.0.1:5000/api/v1/stats
```

## Error format

Errors are returned as JSON:

```json
{
  "error": "validation_error",
  "message": "..."
}
```
