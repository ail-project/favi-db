from __future__ import annotations


def build_openapi_spec() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "favi-db API",
            "version": "1.0.0",
            "description": "API for storing and searching favicon hashes and metadata.",
        },
        "servers": [{"url": "/api/v1"}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "Token",
                }
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["error"],
                },
                "FaviconPayload": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "example": "example.org"},
                        "url": {
                            "type": "string",
                            "format": "uri",
                            "example": "https://example.org/favicon.ico",
                        },
                        "hashes": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                            "example": {
                                "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                                "sha1": "dummy",
                                "md5": "dummy",
                                "mmh3": "-123456789",
                            },
                        },
                        "favicon_base64": {
                            "type": "string",
                            "description": "Optional raw favicon bytes in base64; used only to compute hashes and discarded.",
                        },
                        "metadata": {"type": "object"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "example": ["seed"],
                        },
                    },
                },
            },
        },
        "paths": {
            "/health": {
                "get": {
                    "summary": "API health check",
                    "responses": {"200": {"description": "Service healthy"}},
                }
            },
            "/favicons": {
                "post": {
                    "summary": "Insert or update favicon metadata",
                    "security": [{"bearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/FaviconPayload"}
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Created"},
                        "400": {
                            "description": "Validation error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"}
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                    },
                }
            },
            "/favicons/{sha256}": {
                "get": {
                    "summary": "Get favicon record by SHA-256",
                    "parameters": [
                        {
                            "name": "sha256",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Record found"},
                        "404": {"description": "Not found"},
                    },
                }
            },
            "/search": {
                "get": {
                    "summary": "Search favicon records",
                    "description": "Use one of: algo+value, host, or tag.",
                    "parameters": [
                        {"name": "algo", "in": "query", "schema": {"type": "string"}},
                        {"name": "value", "in": "query", "schema": {"type": "string"}},
                        {"name": "hash", "in": "query", "schema": {"type": "string"}},
                        {"name": "host", "in": "query", "schema": {"type": "string"}},
                        {"name": "tag", "in": "query", "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"description": "Search results"}, "400": {"description": "Invalid query"}},
                }
            },
            "/stats": {
                "get": {
                    "summary": "Aggregate backend stats",
                    "responses": {"200": {"description": "Statistics"}},
                }
            },
        },
    }
