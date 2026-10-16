"""Content-addressed caching: identical (inputs + engine + spec) => identical key.

A cache hit means the deterministic engine has already produced this exact
output — re-runs are free and byte-identical.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_digest(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def content_key(
    source_paths: list[str | Path], engine_version: str, canonical_spec: str
) -> str:
    h = hashlib.sha256()
    h.update(engine_version.encode())
    h.update(b"\0")
    h.update(canonical_spec.encode())
    for p in sorted(str(x) for x in source_paths):
        h.update(b"\0")
        h.update(file_digest(p).encode())
    return h.hexdigest()[:16]
