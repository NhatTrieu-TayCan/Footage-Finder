"""Disk-based caching with TTL and version-keyed hashing."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def compute_cache_key(identifier: str, version: str, content: Any) -> str:
    """Compute SHA-256 cache key from identifier, version, and serialized content."""
    if isinstance(content, (dict, list)):
        serialized = json.dumps(content, sort_keys=True)
    elif isinstance(content, bytes):
        serialized = content.hex()
    else:
        serialized = str(content)
    raw = f"{identifier}::{version}::{serialized}".encode()
    return hashlib.sha256(raw).hexdigest()


class DiskCache:
    def __init__(self, base_dir: Path = Path(".cache/footage_finder")):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _category_dir(self, category: str) -> Path:
        d = self.base_dir / category
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_json(
        self, category: str, key: str, max_age_seconds: float | None = None
    ) -> Any | None:
        cat_dir = self._category_dir(category)
        path = cat_dir / f"{key}.json"
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                envelope = json.load(f)
            created_at = envelope.get("_cached_at", 0)
            if max_age_seconds is not None and (
                time.time() - created_at > max_age_seconds
            ):
                # Expired
                return None
            return envelope.get("data")
        except (json.JSONDecodeError, OSError):
            return None

    def set_json(self, category: str, key: str, value: Any) -> None:
        cat_dir = self._category_dir(category)
        path = cat_dir / f"{key}.json"
        envelope = {
            "_cached_at": time.time(),
            "data": value,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2, default=str)

    def get_file(self, category: str, key: str, ext: str = ".jpg") -> Path | None:
        cat_dir = self._category_dir(category)
        path = cat_dir / f"{key}{ext}"
        if path.exists() and path.stat().st_size > 0:
            return path
        return None

    def save_file(
        self, category: str, key: str, data: bytes, ext: str = ".jpg"
    ) -> Path:
        cat_dir = self._category_dir(category)
        path = cat_dir / f"{key}{ext}"
        with open(path, "wb") as f:
            f.write(data)
        return path

    def clear(self, category: str | None = None) -> int:
        count = 0
        target = self._category_dir(category) if category else self.base_dir
        if not target.exists():
            return 0
        for p in target.glob("**/*"):
            if p.is_file():
                try:
                    p.unlink()
                    count += 1
                except OSError:
                    continue
        return count
