"""The `gateprobe` command: expand, run, replay, analyze, report, ci, hook.

Scope of v0: `expand` (C4/C5) writes base items and the deterministic
variants; `run` and `replay` (R2; Message Batches for the Claude judge, R8)
send a variants file through one gate and write the rows to
runs/<run_id>.jsonl; `analyze` (R6), `report` (I1) and `ci` (I3) score,
render and check them; `hook` (I2) is the Claude Code PreToolUse hook.
`PLANNED` lists any subcommand still to come (it exits 3, naming its step).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from gateprobe import __version__

NOT_IMPLEMENTED = 3
ROOT = Path(__file__).resolve().parents[2]

# subcommand -> (help text, plan step that implements it)
PLANNED: dict[str, tuple[str, str]] = {}
RUNS = {
    "run": "send a variants file x repeats through one gate (cache first, then the gate, under the $ cap)",
    "replay": "re-run a variants file from the response cache only; needs no API key, fails on any miss",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gateprobe", description="Metamorphic testing of coding-agent permission gates."
    )
    parser.add_argument("--version", action="version", version=f"gateprobe {__version__}")
    names = [*PLANNED, *RUNS, "expand", "analyze", "report", "hook", "ci"]
    sub = parser.add_subparsers(dest="command", metavar="{" + ",".join(sorted(names)) + "}")
    for name, (help_text, step) in PLANNED.items():
        sub.add_parser(name, help=help_text, description=f"{help_text} (built in step {step}).")
    ex = sub.add_parser(
        "expand",
        help="generate base items and the deterministic relation variants from the probe corpus",
        description="Write variants/generated.jsonl (base items + all applicable variants); print counts.",
    )
    ex.add_argument("--config", type=Path, default=ROOT / "configs" / "relations.yaml")
    rp = sub.add_parser(
        "report",
        help="render runs as one self-contained HTML report",
        description="Flip table with intervals, reliability diagram, top-20 flips before/after, band, cost.",
    )
    rp.add_argument("--runs", nargs="+", required=True, type=Path, help="run JSONL files (any gates)")
    rp.add_argument("--variants", nargs="+", type=Path, default=[ROOT / "variants" / "generated.jsonl"])
    rp.add_argument("--probes", type=Path, default=ROOT / "probes" / "corpus.jsonl", help="for the labels")
    rp.add_argument("--out", type=Path, default=ROOT / "reports" / "report.html")
    rp.add_argument("--title", default="GateProbe report")
    from gateprobe.report.ci import RULE

    ci = sub.add_parser(
        "ci",
        help="exit non-zero when a relation's flip rate above the floor exceeds --max-flip",
        description=f"The check {RULE}. Exit codes: 0 pass, 1 fail, 2 no scorable data.",
    )
    ci.add_argument("--runs", nargs="+", required=True, type=Path, help="run JSONL files (any gates)")
    ci.add_argument("--max-flip", type=float, default=0.05, help="largest tolerated excess (default 0.05)")
    ci.add_argument("--classes", default="", help="comma-separated relation classes to check (default: all)")
    hk = sub.add_parser(
        "hook",
        help="Claude Code PreToolUse hook: read the call on stdin, print the gate's verdict as JSON",
        description="Advisory by default; --enforce may deny, never approve. Reads the cache first.",
    )
    hk.add_argument("--gate", default="jev", help="gate name in configs/gates.yaml")
    hk.add_argument("--policy", default="workspace-dev", help="policy id under policies/")
    hk.add_argument("--rendering", default="yaml", choices=["yaml", "json", "prose", "bullets"])
    hk.add_argument(
        "--results", type=Path, help="results/<name>/ from gateprobe analyze, for fragility warnings"
    )
    hk.add_argument(
        "--replay-only", action="store_true", help="answer from the cache only; never call an API"
    )
    hk.add_argument("--enforce", action="store_true", help="deny the call when the gate denies it")
    hk.add_argument("--gates-config", type=Path, default=ROOT / "configs" / "gates.yaml")
    hk.add_argument("--run-config", type=Path, default=ROOT / "configs" / "run.yaml")
    an = sub.add_parser(
        "analyze",
        help="score run JSONL files as pre-registered in docs/RELATIONS.md and write results/<name>/*.csv",
        description="Score runs per gate: floor, flips above it, M inversions, A shifts, band, ECE, cost.",
    )
    an.add_argument("--runs", nargs="+", required=True, type=Path, help="run JSONL files (any gates)")
    an.add_argument("--name", required=True, help="results/<name>/ (must not exist: results are append-only)")
    an.add_argument("--probes", type=Path, default=ROOT / "probes" / "corpus.jsonl", help="for the labels")
    an.add_argument(
        "--variants", nargs="*", type=Path, default=[], help="variant files (top-transform examples)"
    )
    for name, help_text in RUNS.items():
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument("--gate", required=True, help="gate name in configs/gates.yaml, e.g. jev")
        p.add_argument("--variants", required=True, type=Path, help="variants JSONL (base items included)")
        p.add_argument("--repeats", type=int, help="override configs/run.yaml repeats")
        p.add_argument("--run-id", help="default: <gate>-<UTC timestamp>")
        p.add_argument("--limit", type=int, help="only the first N variants (smoke runs)")
        p.add_argument("--workers", type=int, default=1, help="parallel calls (the cap is checked per chunk)")
        p.add_argument("--gates-config", type=Path, default=ROOT / "configs" / "gates.yaml")
        p.add_argument("--run-config", type=Path, default=ROOT / "configs" / "run.yaml")
    return parser


def cmd_run(args: argparse.Namespace, replay: bool) -> int:
    from gateprobe.config import load_gates, load_run
    from gateprobe.corpus.schema import Variant, load_jsonl
    from gateprobe.env import load_dotenv
    from gateprobe.gates.factory import make_gate
    from gateprobe.runner.cache import Cache
    from gateprobe.runner.run import CapReached, ReplayMiss, config_hash, run_gate

    gates = load_gates(args.gates_config)
    run_cfg = load_run(args.run_config, gates=gates)
    if args.gate not in gates:
        print(f"gateprobe: no gate {args.gate!r} in {args.gates_config}", file=sys.stderr)
        return 2
    if not replay:
        load_dotenv()
    cfg = gates[args.gate]
    gate = make_gate(cfg)
    variants = load_jsonl(args.variants, Variant)[: args.limit]
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_id or f"{cfg.name}-{stamp}"
    out = ROOT / run_cfg.runs_dir / f"{run_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    code = 0
    batched = cfg.options.get("backend") == "anthropic" and cfg.options.get("batch", True) and not replay
    with out.open("w", encoding="utf-8") as f:
        try:
            rows = run_gate(
                variants,
                gate,
                repeats=args.repeats or run_cfg.repeats,
                cache=Cache(ROOT / run_cfg.cache_dir),
                run_id=run_id,
                cap_usd=run_cfg.caps_usd[cfg.name],
                config_digest=config_hash(cfg, run_cfg),
                replay=replay,
                retry=run_cfg.retry,
                spend_csv=ROOT / run_cfg.spend_csv,
                workers=args.workers,
            )
            if batched:
                from gateprobe.runner.batch import run_batched

                print(f"{run_id}: submitting/collecting Message Batches (resume with --run-id {run_id})")
                rows = run_batched(
                    variants,
                    gate,
                    repeats=args.repeats or run_cfg.repeats,
                    cache=Cache(ROOT / run_cfg.cache_dir),
                    run_id=run_id,
                    cap_usd=run_cfg.caps_usd[cfg.name],
                    config_digest=config_hash(cfg, run_cfg),
                    state_path=ROOT / run_cfg.runs_dir / f"{run_id}.batches.json",
                    est_usd_per_call=cfg.options.get("est_usd_per_call"),
                    spend_csv=ROOT / run_cfg.spend_csv,
                )
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                counts[row["status"] + ("/cached" if row.get("cached") else "")] += 1
        except (CapReached, ReplayMiss) as e:
            print(f"gateprobe {args.command}: stopped: {e}", file=sys.stderr)
            code = 1
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"{run_id}: {dict(sorted(counts.items()))} -> {shown}")
    return code


def cmd_expand(args: argparse.Namespace) -> int:
    from gateprobe.relations.expand import counts_table, run, to_jsonl

    variants, skips, out = run(args.config, ROOT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_jsonl(variants), encoding="utf-8")
    print(counts_table(variants, skips))
    print(f"{len(variants)} items -> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


def _labels(probes_path: Path) -> dict[str, str]:
    """Labels on the corpus records, then the majority of probes/labels.jsonl (next to the corpus) on top."""
    from gateprobe.corpus.labels import majority, read_labels
    from gateprobe.corpus.schema import Probe, load_jsonl

    labels = {p.id: p.label for p in load_jsonl(probes_path, Probe) if p.label}
    labels |= majority(read_labels(Path(probes_path).parent / "labels.jsonl"))
    return labels


def cmd_analyze(args: argparse.Namespace) -> int:
    from gateprobe.analysis.score import score
    from gateprobe.analysis.write import write

    rows = [
        json.loads(line)
        for path in args.runs
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    labels = _labels(args.probes)
    spend_csv = ROOT / "results" / "spend.csv"
    spend = list(csv.DictReader(spend_csv.open(encoding="utf-8"))) if spend_csv.exists() else []
    submitted = {}
    for path in args.runs:  # batch runs keep runs/<run_id>.batches.json next to their rows
        state = path.with_name(f"{path.stem}.batches.json")
        if state.exists():
            d = json.loads(state.read_text(encoding="utf-8"))
            stamps = [b["submitted_at"] for b in d.get("batches", []) if b.get("submitted_at")]
            if stamps:
                submitted[d.get("run_id", path.stem)] = min(stamps)
    scored = score(rows, labels or None, spend or None, submitted)
    if args.variants:
        from gateprobe.corpus.schema import Variant, load_jsonl

        by_id = {v.id: v for path in args.variants for v in load_jsonl(path, Variant)}
        for t in scored.get("top_transforms", []):
            t["parent_input"] = _describe(by_id.get(t["parent_id"]))
            t["variant_input"] = _describe(by_id.get(t["variant_id"]))
    out = ROOT / "results" / args.name
    written = write(scored, out, [str(p) for p in args.runs])
    print(f"{len(rows)} rows -> {len(written)} tables in {out.relative_to(ROOT)}")
    return 0


def _describe(v: Any) -> str:
    """What a gate was asked, in one line: the call, then whatever the transform changed."""
    from gateprobe.corpus.schema import DEFAULT_OPTION_NAMES

    if v is None:
        return ""
    parts = [f"{v.tool} {json.dumps(v.call, sort_keys=True)}"]
    if v.policy_rendering != "yaml":
        parts.append(f"policy as {v.policy_rendering}")
    if v.policy_text:
        parts.append(f"policy text: {v.policy_text[:200]}")
    if v.context:
        parts.append(f"context: {v.context[:200]}")
    if v.option_names != DEFAULT_OPTION_NAMES:
        parts.append(f"options: {json.dumps(v.option_names, sort_keys=True)}")
    return " | ".join(parts)


def cmd_report(args: argparse.Namespace) -> int:
    from gateprobe.corpus.schema import Variant, load_jsonl
    from gateprobe.report.html import render

    rows = [
        json.loads(line)
        for path in args.runs
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    variants = [v for path in args.variants for v in load_jsonl(path, Variant)]
    labels = _labels(args.probes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(rows, variants, labels or None, args.title), encoding="utf-8")
    print(f"{len(rows)} rows -> {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "expand":
        return cmd_expand(args)
    if args.command == "analyze":
        return cmd_analyze(args)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "ci":
        from gateprobe.report.ci import check

        rows = [
            json.loads(line)
            for path in args.runs
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        classes = {c.strip() for c in args.classes.split(",") if c.strip()} or None
        code, lines = check(rows, args.max_flip, classes)
        print("\n".join(lines))
        return code
    if args.command == "hook":
        from gateprobe.hook.claude_code import main as hook_main

        return hook_main(args)
    if args.command in RUNS:
        return cmd_run(args, replay=args.command == "replay")
    step = PLANNED[args.command][1]
    print(
        f"gateprobe {args.command}: not implemented yet — step {step} in docs/PLAN.md builds it",
        file=sys.stderr,
    )
    return NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main())
