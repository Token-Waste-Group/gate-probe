"""Load and validate `configs/gates.yaml` and `configs/run.yaml`.

Scope of v0: parsing into frozen records, with the checks the invariants need
before any call is made — every gate uses a known adapter and a pinned model
id, and every gate has a $ cap. Out of scope: config hashing for provenance
(the runner, R2) and adapter-specific options (each adapter validates its own).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# The repo's configs/ (editable install). An installed wheel passes paths explicitly.
CONFIGS = Path(__file__).resolve().parents[2] / "configs"
ADAPTERS = frozenset({"decisions", "judge", "rules", "http"})
# Aliases that silently move to a new model version. A pinned id names a version.
FLOATING = re.compile(r"latest|preview|default|auto|stable", re.IGNORECASE)


class ConfigError(ValueError):
    pass


def is_pinned(model_id: str) -> bool:
    """True when `model_id` names a fixed version (it has a digit and no floating alias)."""
    return bool(model_id) and not FLOATING.search(model_id) and any(c.isdigit() for c in model_id)


@dataclass(frozen=True)
class GateConfig:
    name: str
    adapter: str
    model: str
    options: dict[str, Any]


@dataclass(frozen=True)
class RunConfig:
    seed: int
    repeats: int
    retry: dict[str, float]
    caps_usd: dict[str, float]
    cache_dir: str
    runs_dir: str
    spend_csv: str


def _read(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return data


def load_gates(path: Path = CONFIGS / "gates.yaml") -> dict[str, GateConfig]:
    gates = _read(path).get("gates")
    if not isinstance(gates, dict) or not gates:
        raise ConfigError(f"{path}: needs a non-empty `gates:` mapping")
    out: dict[str, GateConfig] = {}
    for name, spec in gates.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"{path}: gate {name!r} must be a mapping")
        adapter, model = spec.get("adapter"), str(spec.get("model") or "")
        if adapter not in ADAPTERS:
            raise ConfigError(
                f"{path}: gate {name!r} has adapter {adapter!r}; expected one of {sorted(ADAPTERS)}"
            )
        if not is_pinned(model):
            raise ConfigError(f"{path}: gate {name!r} model {model!r} is not a pinned version")
        options = {k: v for k, v in spec.items() if k not in ("adapter", "model")}
        out[name] = GateConfig(name=name, adapter=adapter, model=model, options=options)
    return out


def load_run(path: Path = CONFIGS / "run.yaml", gates: dict[str, GateConfig] | None = None) -> RunConfig:
    data = _read(path)
    try:
        run = RunConfig(
            seed=int(data["seed"]),
            repeats=int(data["repeats"]),
            retry={k: float(v) for k, v in data.get("retry", {}).items()},
            caps_usd={k: float(v) for k, v in data["caps_usd"].items()},
            cache_dir=str(data.get("cache_dir", "cache")),
            runs_dir=str(data.get("runs_dir", "runs")),
            spend_csv=str(data.get("spend_csv", "results/spend.csv")),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ConfigError(f"{path}: {e!r}") from e
    if run.repeats < 1:
        raise ConfigError(f"{path}: repeats must be >= 1")
    if any(cap < 0 for cap in run.caps_usd.values()):
        raise ConfigError(f"{path}: $ caps must be >= 0")
    missing = sorted(set(gates or {}) - set(run.caps_usd))
    if missing:
        raise ConfigError(f"{path}: no $ cap for gates {missing}")
    return run
