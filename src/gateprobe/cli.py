"""The `gateprobe` command: expand, run, report, ci, replay.

Scope of v0: `expand` (C4) writes base items and the deterministic variants;
`run` and `replay` (R2) send a variants file through one gate and write the
rows to runs/<run_id>.jsonl; `analyze` (R6) and `report` (I1) score and
render them; the others have `--help` and exit with
status 3, naming the plan step that builds them. Out of scope: the planned
subcommands' behavior (see `PLANNED`).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from collections import Counter
from pathlib import Path

from gateprobe import __version__

NOT_IMPLEMENTED = 3
ROOT = Path(__file__).resolve().parents[2]

# subcommand -> (help text, plan step that implements it)
PLANNED: dict[str, tuple[str, str]] = {
    "ci": ("fail when a relation's flip rate exceeds --max-flip", "I3"),
}
RUNS = {
    "run": "send a variants file x repeats through one gate (cache first, then the gate, under the $ cap)",
    "replay": "re-run a variants file from the response cache only; needs no API key, fails on any miss",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gateprobe", description="Metamorphic testing of coding-agent permission gates."
    )
    parser.add_argument("--version", action="version", version=f"gateprobe {__version__}")
    names = [*PLANNED, *RUNS, "expand", "analyze", "report"]
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
    an = sub.add_parser(
        "analyze",
        help="score run JSONL files as pre-registered in docs/RELATIONS.md and write results/<name>/*.csv",
        description="Score runs per gate: floor, flips above it, M inversions, A shifts, band, ECE, cost.",
    )
    an.add_argument("--runs", nargs="+", required=True, type=Path, help="run JSONL files (any gates)")
    an.add_argument("--name", required=True, help="results/<name>/ (must not exist: results are append-only)")
    an.add_argument("--probes", type=Path, default=ROOT / "probes" / "corpus.jsonl", help="for the labels")
    for name, help_text in RUNS.items():
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument("--gate", required=True, help="gate name in configs/gates.yaml, e.g. jev")
        p.add_argument("--variants", required=True, type=Path, help="variants JSONL (base items included)")
        p.add_argument("--repeats", type=int, help="override configs/run.yaml repeats")
        p.add_argument("--run-id", help="default: <gate>-<UTC timestamp>")
        p.add_argument("--limit", type=int, help="only the first N variants (smoke runs)")
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


def cmd_analyze(args: argparse.Namespace) -> int:
    from gateprobe.analysis.score import score
    from gateprobe.analysis.write import write
    from gateprobe.corpus.schema import Probe, load_jsonl

    rows = [
        json.loads(line)
        for path in args.runs
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    labels = {p.id: p.label for p in load_jsonl(args.probes, Probe) if p.label}
    out = ROOT / "results" / args.name
    written = write(score(rows, labels or None), out, [str(p) for p in args.runs])
    print(f"{len(rows)} rows -> {len(written)} tables in {out.relative_to(ROOT)}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from gateprobe.corpus.schema import Probe, Variant, load_jsonl
    from gateprobe.report.html import render

    rows = [
        json.loads(line)
        for path in args.runs
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    variants = [v for path in args.variants for v in load_jsonl(path, Variant)]
    labels = {p.id: p.label for p in load_jsonl(args.probes, Probe) if p.label}
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
