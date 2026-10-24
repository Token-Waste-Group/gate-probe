"""Write a scored analysis as distilled CSVs (results/<name>/*.csv) — the numbers the paper uses.

Scope of v0: one CSV per table (floor, relations, transforms, sensitivity,
majority_inversions, threshold_band, threshold_curve, calibration,
reliability, cost) plus meta.csv (Bonferroni family size, z values, inputs).
Floats are written with 6 decimals. A directory is written once: an existing
one is never overwritten (results/ is append-only). Out of scope: plots (R7).
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


def _fmt(v: Any) -> Any:
    if isinstance(v, float):
        return "" if math.isnan(v) else f"{v:.6f}"
    return v


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(v) for k, v in r.items()})


def write(scored: dict[str, Any], out: Path, inputs: list[str]) -> list[Path]:
    if out.exists():
        raise FileExistsError(f"{out} exists; results are append-only, pick a new name")
    out.mkdir(parents=True)
    written = []
    curve_rows, reliability_rows = [], []
    for band in scored.get("threshold_band", []):
        for tau, rate in (band.get("crossing_curve") or {}).items():
            curve_rows.append({"gate_id": band["gate_id"], "tau": tau, "crossing_rate": rate})
    for cal in scored.get("calibration", []):
        for b in cal.get("reliability") or []:
            reliability_rows.append({"gate_id": cal["gate_id"], **b})
    nested = (
        "crossing_curve",
        "reliability",
    )  # flattened into their own tables above; the input is not mutated
    tables = {
        k: [{f: x for f, x in r.items() if f not in nested} for r in v]
        for k, v in scored.items()
        if isinstance(v, list)
    }
    tables |= {"threshold_curve": curve_rows, "reliability": reliability_rows}
    tables["meta"] = [
        {
            "bonferroni_tests": scored["bonferroni_tests"],
            "z_95": scored["z_95"],
            "z_bonferroni": scored["z_bonferroni"],
            "inputs": ";".join(inputs),
        }
    ]
    for name, rows in tables.items():
        if rows:
            p = out / f"{name}.csv"
            _write(p, rows)
            written.append(p)
    return written
