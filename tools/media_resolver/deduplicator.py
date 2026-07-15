from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def existing_checksums(directory: Path) -> dict[str, Path]:
    values: dict[str, Path] = {}
    if directory.exists():
        for path in directory.rglob("*"):
            if path.is_file() and path.name != "media_manifest.json":
                values[sha256_bytes(path.read_bytes())] = path
    return values
