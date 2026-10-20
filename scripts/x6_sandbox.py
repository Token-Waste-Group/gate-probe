#!/usr/bin/env python3
"""X6: run both commands of every P command pair in a throwaway sandbox and compare their effects.

Pre-registered in docs/experiments/x6-p-sandbox.md. Each command runs alone in a fresh container from
the fixture image (scripts/x6/), with --network none. Its effect signature is:
- the exit status class;
- the files under the observed roots;
- the git state;
- the paths changed elsewhere (docker diff);
- the files it opened.

A pair is classed `not_runnable`, `same_effect` (it survives as equivalent) or `different_effect`.
Every parent also runs a second time, as a check that the sandbox itself is deterministic. The
frozen runs are then re-scored with the pre-registered scorer on row subsets: every command rewrite,
the survivors, the different-effect pairs.

    docker build -t gateprobe-x6 scripts/x6
    uv run python scripts/x6_sandbox.py --image gateprobe-x6 --name x6-p-sandbox [--workers 2]

Writes results/<name>/{pairs,self_check,p_rates,meta}.csv (append-only: the directory must not exist).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ("x1-jev", "x4p-jev", "x1-rules", "x4p-rules", "x7-claude", "x4p-claude")
FROZEN += ("x3-luna", "x4p-luna", "x3-pplx", "x4p-pplx", "x3-drex", "x4p-drex")
NETWORK = re.compile(
    r"https?://|git\+|\b[\w.-]+@[\w.-]+[:\s']|\bssh\b|\bpip3?\s+install\b|-m\s+pip\s+install\b|\bensurepip\b"
)
MISSING_TOOLS = re.compile(
    r"\b(npm|npx|yarn|pnpm|node|cargo|rustc|rustfmt|clippy|go|gofmt|gradle|mvn|poetry|uv|brew)\b"
)
UNOBSERVED = ("/tmp", "/work", "/home/agent", "/var/log/app", "/remote", "/proc", "/dev", "/sys")
ANCESTORS = {"/home", "/var", "/var/log"}  # docker diff marks the parents of a changed root as changed
COMPONENTS = ("status", "files", "git", "system", "opened")
DOCKER_RUN = ("--network", "none", "--cap-add", "SYS_PTRACE", "--security-opt", "seccomp=unconfined")


def pairs(root: Path = ROOT) -> list[dict[str, str]]:
    base = {}
    for line in (root / "variants" / "generated.jsonl").read_text(encoding="utf-8").splitlines():
        v = json.loads(line)
        base[v["id"]] = v
    tiers = {}
    for line in (root / "probes" / "corpus.jsonl").read_text(encoding="utf-8").splitlines():
        p = json.loads(line)
        tiers[p["id"]] = p["risk_tier"]
    out = []
    for line in (root / "variants" / "paraphrase.jsonl").read_text(encoding="utf-8").splitlines():
        v = json.loads(line)
        if v["transform"] != "command_paraphrase":
            continue
        out.append(
            {
                "variant_id": v["id"],
                "parent_id": v["parent_id"],
                "probe_id": v["probe_id"],
                "tier": tiers[v["probe_id"]],
                "parent_cmd": base[v["parent_id"]]["call"]["command"],
                "variant_cmd": v["call"]["command"],
            }
        )
    return out


def needs_network_or_missing_tool(cmd: str) -> bool:
    return bool(NETWORK.search(cmd) or MISSING_TOOLS.search(cmd))


def run(image: str, cmd: str, docker: tuple[str, ...] = ("docker",)) -> dict[str, Any]:
    """One command in a fresh container: the snapshot JSON plus the changed paths outside the roots."""
    name = f"x6-{uuid.uuid4().hex[:12]}"
    subprocess.run(
        [*docker, "create", "--name", name, *DOCKER_RUN, image, cmd], check=True, capture_output=True
    )
    try:
        r = subprocess.run([*docker, "start", "-a", name], capture_output=True, text=True, timeout=120)
        sig = json.loads(r.stdout)
        diff = subprocess.run([*docker, "diff", name], capture_output=True, text=True, check=True).stdout
        sig["system"] = system_changes(diff)
        return sig
    finally:
        subprocess.run([*docker, "rm", "-f", name], capture_output=True)


def system_changes(diff: str) -> list[str]:
    """docker diff lines ('C /etc', 'A /etc/x') outside the observed roots and their parents."""
    return sorted(
        line
        for line in diff.splitlines()
        if not line[2:].startswith(UNOBSERVED) and line[2:] not in ANCESTORS
    )


def differing(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    out = []
    for c in COMPONENTS:
        x, y = a[c], b[c]
        if c == "status":
            x, y = x == 0, y == 0
        if x != y:
            out.append(c)
    return out


def classify(pair: dict[str, str], a: dict[str, Any], b: dict[str, Any]) -> tuple[str, list[str]]:
    if any(needs_network_or_missing_tool(pair[k]) for k in ("parent_cmd", "variant_cmd")) or 127 in (
        a["status"],
        b["status"],
    ):
        return "not_runnable", []
    diff = differing(a, b)
    return ("different_effect" if diff else "same_effect"), diff


def p_rates(subsets: dict[str, set[str]], root: Path = ROOT) -> list[dict[str, Any]]:
    """The pre-registered P statistics on each subset of command rewrites. Each gate's floor (f, delta)
    comes from all its frozen rows, exactly as in results/x4-final; only the P pairs are restricted."""
    sys.path.insert(0, str(root / "src"))
    from gateprobe.analysis.score import floor, index, relation_stats

    rows = [
        json.loads(line)
        for run_id in FROZEN
        for line in (root / "runs" / f"{run_id}.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    meta = next(csv.DictReader((root / "results" / "x4-final" / "meta.csv").open(encoding="utf-8")))
    z_bonf = float(meta["z_bonferroni"])
    floors = {gid: floor(g) for gid, g in index(rows).items()}
    base = [r for r in rows if r["relation_class"] == "base"]
    out = []
    for subset, ids in subsets.items():
        for gid, g in sorted(index(base + [r for r in rows if r["variant_id"] in ids]).items()):
            r = relation_stats(g, floors[gid], "P", None, z_bonf)
            out.append({"subset": subset, **{k: r.get(k) for k in P_FIELDS}})
    return out


P_FIELDS = ("gate_id", "n_pairs", "floor_f", "rate", "rate_lo", "rate_hi")
P_FIELDS += ("excess", "excess_lo", "excess_hi", "label")


def subsets_of(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    """The pre-registered subsets, plus two post hoc views: the survivors where both commands
    succeeded (no "both failed, nothing changed"), and the pairs that differ in nothing but the files
    they opened (same writes, same state, same exit class)."""
    return {
        "all_command_rewrites": {r["variant_id"] for r in rows},
        "same_effect": {r["variant_id"] for r in rows if r["class"] == "same_effect"},
        "different_effect": {r["variant_id"] for r in rows if r["class"] == "different_effect"},
        "post_hoc_same_effect_both_ok": {
            r["variant_id"]
            for r in rows
            if r["class"] == "same_effect"
            and str(r["parent_status"]) == "0"
            and str(r["variant_status"]) == "0"
        },
        "post_hoc_same_writes": {
            r["variant_id"]
            for r in rows
            if r["class"] == "same_effect"
            or (r["class"] == "different_effect" and r["differs_in"] == "opened")
        },
    }


def write(path: Path, rows: list[dict[str, Any]]) -> None:
    """CSV with floats at 6 decimals, like every other table in results/."""
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows({k: f"{v:.6f}" if isinstance(v, float) else v for k, v in r.items()} for r in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", default="gateprobe-x6")
    parser.add_argument("--name", required=True, help="results/<name>/ (must not exist)")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--docker", default="docker", help="the docker command, e.g. 'docker --context colima'"
    )
    parser.add_argument("--rescore", action="store_true", help="only recompute p_rates.csv from pairs.csv")
    args = parser.parse_args()
    out = ROOT / "results" / args.name
    if args.rescore:
        with (out / "pairs.csv").open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        write(out / "p_rates.csv", p_rates(subsets_of(rows)))
        print(f"-> {(out / 'p_rates.csv').relative_to(ROOT)}")
        return 0
    if out.exists():
        raise SystemExit(f"{out} exists; results are append-only")
    docker = tuple(args.docker.split())
    image_id = subprocess.run(
        [*docker, "image", "inspect", "-f", "{{.Id}}", args.image], capture_output=True, text=True, check=True
    ).stdout.strip()
    todo = pairs()
    jobs = [(p["variant_id"], k, p[k]) for p in todo for k in ("parent_cmd", "variant_cmd")]
    jobs += [(p["variant_id"], "parent_again", p["parent_cmd"]) for p in todo]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda j: (j[0], j[1], run(args.image, j[2], docker)), jobs))
    sig = {(vid, k): s for vid, k, s in results}
    rows, checks = [], []
    for p in todo:
        a, b, again = (
            sig[(p["variant_id"], "parent_cmd")],
            sig[(p["variant_id"], "variant_cmd")],
            sig[(p["variant_id"], "parent_again")],
        )
        cls, diff = classify(p, a, b)
        rows.append(
            {
                **p,
                "class": cls,
                "differs_in": ";".join(diff),
                "parent_status": a["status"],
                "variant_status": b["status"],
            }
        )
        checks.append(
            {
                "variant_id": p["variant_id"],
                "parent_cmd": p["parent_cmd"],
                "deterministic": not differing(a, again),
                "differs_in": ";".join(differing(a, again)),
            }
        )
    out.mkdir(parents=True)
    write(out / "pairs.csv", rows)
    write(out / "self_check.csv", checks)
    write(out / "p_rates.csv", p_rates(subsets_of(rows)))
    write(
        out / "meta.csv",
        [{"image_id": image_id, "pairs": len(rows), "runs": len(jobs), "frozen_runs": ";".join(FROZEN)}],
    )
    counts = {
        c: sum(r["class"] == c for r in rows) for c in ("same_effect", "different_effect", "not_runnable")
    }
    stable = sum(c["deterministic"] for c in checks)
    print(f"{len(rows)} pairs: {counts}; self-check deterministic {stable}/{len(checks)}")
    print(f"-> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
