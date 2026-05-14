from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any

import mmh3


@dataclass(frozen=True)
class FaviconHashes:
    md5: str
    sha1: str
    sha256: str
    sha512: str
    mmh3: str
    mmh3_unsigned: str
    mmh3_raw: str
    mmh3_raw_unsigned: str

    def as_dict(self) -> dict[str, str]:
        return {
            "md5": self.md5,
            "sha1": self.sha1,
            "sha256": self.sha256,
            "sha512": self.sha512,
            "mmh3": self.mmh3,
            "mmh3_unsigned": self.mmh3_unsigned,
            "mmh3_raw": self.mmh3_raw,
            "mmh3_raw_unsigned": self.mmh3_raw_unsigned,
        }


def compute_hashes(content: bytes) -> FaviconHashes:
    """Compute raw cryptographic hashes and favicon-oriented MurmurHash3 values.

    `mmh3` is the signed 32-bit MurmurHash3 over base64-encoded favicon bytes,
    matching the convention commonly used by Shodan-style favicon searches.

    `mmh3_raw` is also stored because it can be useful internally, but the API
    treats `mmh3` as the default favicon hash.
    """

    b64 = base64.encodebytes(content)
    return FaviconHashes(
        md5=hashlib.md5(content, usedforsecurity=False).hexdigest(),
        sha1=hashlib.sha1(content, usedforsecurity=False).hexdigest(),
        sha256=hashlib.sha256(content).hexdigest(),
        sha512=hashlib.sha512(content).hexdigest(),
        mmh3=str(mmh3.hash(b64, signed=True)),
        mmh3_unsigned=str(mmh3.hash(b64, signed=False)),
        mmh3_raw=str(mmh3.hash(content, signed=True)),
        mmh3_raw_unsigned=str(mmh3.hash(content, signed=False)),
    )


def compute_hashes_from_base64(value: str) -> dict[str, Any]:
    """Decode a base64 blob, compute hashes, and discard the original bytes."""

    return compute_hashes(base64.b64decode(value, validate=True)).as_dict()
