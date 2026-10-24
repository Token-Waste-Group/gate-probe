"""The content-addressed response cache — the source of truth for every gate answer, and the replay mode.

Scope of v0: one JSON file per call at `cache/<sha256>.json`, keyed on (gate id,
pinned model id, mode, exact request bytes, repeat index). The repeat index is
in the key, so repeats are real repeated calls, never cache hits of one another.
Entries are written once and never rewritten. Out of scope: bundling the cache
for reviewers (I5).
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any


def cache_key(gate_id: str, model_id: str, mode: str, request_bytes: bytes, repeat: int) -> str:
    h = hashlib.sha256()
    for part in (gate_id, model_id, mode, str(repeat)):
        h.update(part.encode("utf-8") + b"\x00")
    h.update(request_bytes)
    return h.hexdigest()


class Cache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self.path(key)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, key: str, entry: dict[str, Any]) -> None:
        p = self.path(key)
        if p.exists():
            raise FileExistsError(f"cache entry {key} already exists; entries are never rewritten")
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(
            f".{key}.{uuid.uuid4().hex}.tmp"
        )  # unique per writer: concurrent puts can't collide
        tmp.write_text(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            os.link(tmp, p)  # atomic and exclusive: never a half-written entry, never a rewrite
        except FileExistsError as e:
            raise FileExistsError(f"cache entry {key} already exists; entries are never rewritten") from e
        finally:
            tmp.unlink(missing_ok=True)
