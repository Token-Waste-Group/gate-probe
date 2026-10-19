"""Expand the probe corpus into base items plus every applicable variant of the deterministic classes.

Scope of v0: base items for every probe, then each registered generator in
catalog order (E and I now; M and A arrive with C5). Every variant is built by
`make_variant`, so it passes the schema. Ids are unique and the output is
deterministic. Out of scope: the P class (model-generated, frozen separately by C8).
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from gateprobe.corpus.schema import TRANSFORMS, Probe, Variant, load_jsonl
from gateprobe.relations import equivalence, irrelevance
from gateprobe.relations.common import Generator, base_item, make_variant, seed_for

REGISTRY: dict[str, dict[str, Generator]] = {"E": equivalence.GENERATORS, "I": irrelevance.GENERATORS}


def load_params(path: Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def expand(probes: list[Probe], params: dict[str, Any]) -> tuple[list[Variant], Counter[tuple[str, str]]]:
    """(base items + variants, skips per (class, transform))."""
    out: list[Variant] = []
    skips: Counter[tuple[str, str]] = Counter()
    for probe in probes:
        out.append(base_item(probe))
        for cls, transforms in TRANSFORMS.items():
            generators = REGISTRY.get(cls, {})
            for transform in transforms:
                if transform not in generators:
                    continue
                seed = seed_for(int(params["seed"]), probe.id, transform)
                changes = generators[transform](probe, random.Random(seed), params)
                if not changes:
                    skips[(cls, transform)] += 1
                for n, change in enumerate(changes):
                    out.append(make_variant(probe, cls, transform, n, seed, change))
    return out, skips


def counts_table(variants: list[Variant], skips: Counter[tuple[str, str]]) -> str:
    made = Counter((v.relation_class, v.transform) for v in variants if v.relation_class != "base")
    lines = ["| Class | Transform | Variants | Probes skipped |", "|---|---|---:|---:|"]
    for cls, transforms in TRANSFORMS.items():
        for t in transforms:
            if (cls, t) in made or (cls, t) in skips:
                lines.append(f"| {cls} | `{t}` | {made[(cls, t)]} | {skips[(cls, t)]} |")
    base = sum(v.relation_class == "base" for v in variants)
    lines.append(f"| base | `identity` | {base} | 0 |")
    lines.append(f"| **total** | | **{len(variants)}** | |")
    return "\n".join(lines)


def to_jsonl(variants: list[Variant]) -> str:
    return "".join(json.dumps(v.to_dict(), ensure_ascii=False) + "\n" for v in variants)


def run(params_path: Path, root: Path) -> tuple[list[Variant], Counter[tuple[str, str]], Path]:
    params = load_params(params_path)
    probes = load_jsonl(root / params["probes"], Probe)
    variants, skips = expand(probes, params)
    ids = [v.id for v in variants]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate variant ids")
    return variants, skips, root / params["out"]
