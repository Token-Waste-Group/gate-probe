#!/usr/bin/env python3
"""Render every policy in configs/policies.yaml into policies/<id>/ (YAML, JSON, prose, bullets).

Deterministic; tests/test_policies.py checks the committed files match a fresh render.

    uv run python scripts/render_policies.py
"""

from __future__ import annotations

from pathlib import Path

from gateprobe.corpus.render import load_source, render_all

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = render_all(load_source(ROOT / "configs" / "policies.yaml"))
    for rel, text in files.items():
        out = ROOT / "policies" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(f"{len(files)} renderings -> policies/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
