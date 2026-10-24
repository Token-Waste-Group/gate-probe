"""Load API keys from the repo's git-ignored `.env` into the process environment.

Scope of v0: `KEY=value` lines (comments, blank lines and optional quotes
allowed); variables already set in the environment win; nothing is ever
printed or logged, and the return value holds variable names only. Out of
scope: shell expansion, `export` prefixes, multi-line values.
"""

from __future__ import annotations

import os
from pathlib import Path

DOTENV = Path(__file__).resolve().parents[2] / ".env"


def load_dotenv(path: Path = DOTENV) -> list[str]:
    """Set the variables `path` defines that aren't set yet; return the names that were set."""
    if not Path(path).exists():
        return []
    loaded = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("'\"")
        if name and value and name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded
