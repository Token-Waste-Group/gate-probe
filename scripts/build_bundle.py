#!/usr/bin/env python3
"""Build the replay bundle and the static report page for the frozen runs (I5).

The bundle holds what a reviewer needs to replay every reported gate answer with no API key and
no network: the cache entries behind the 14 runs of the seven-gate evaluation (the twelve frozen
at G3 plus the Gemma judge's two, X2), the run JSONL (with the batch logs RQ4 reads),
BUNDLE.json (the frozen inputs' sha256), a README with the reviewer path, and MANIFEST.sha256
over every file. The archive is deterministic: the same inputs give the same
bytes. The page is `gateprobe report` over the same runs, ready for GitHub Pages.

    uv run python scripts/build_bundle.py [--out dist]

Writes dist/gateprobe-replay-<results>.tar.gz (+ .sha256) and dist/site/index.html (+ .nojekyll).
Publishing both is H5.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE = "19fd14a"  # G3 (human, 2026-10-20): results/ frozen at this commit
RESULTS = "ee08ca1"  # X2 merged; G3 decision 4 added its runs (results/x2-seven-gates/)
FROZEN = (  # the runs behind results/x2-seven-gates/, in the order the analysis read them
    "x1-jev",
    "x4p-jev",
    "x1-rules",
    "x4p-rules",
    "x7-claude",
    "x4p-claude",
    "x3-luna",
    "x4p-luna",
    "x3-pplx",
    "x4p-pplx",
    "x3-drex",
    "x4p-drex",
    "x2-gemma",
    "x2p-gemma",
)
INPUTS = (
    "probes/corpus.jsonl",
    "variants/generated.jsonl",
    "variants/paraphrase.jsonl",
    "configs/gates.yaml",
    "configs/run.yaml",
)
README = """# GateProbe replay bundle ({name})

The cache entries and run files behind every number in the GateProbe paper
(results frozen at commit {freeze}; the Gemma judge's runs added at {results},
before the cut-off). Replay needs no API key and no network.

    shasum -a 256 -c MANIFEST.sha256          # every file intact
    IMAGE=gateprobe                           # or the published image (see the repository README)
    # replay one gate from the cache (a few seconds); drex's frozen run logged one HTTP 520
    # error, which has no cached answer, so --allow-misses records it as replay_miss
    docker run --rm --network none -v "$PWD/cache:/gateprobe/cache:ro" -v "$PWD/runs:/gateprobe/runs" \\
      $IMAGE replay --gate drex --variants variants/generated.jsonl --run-id replay-drex --allow-misses
    # the report over the frozen runs (the hosted page)
    mkdir -p reports
    docker run --rm --network none -v "$PWD/runs:/gateprobe/runs:ro" -v "$PWD/reports:/gateprobe/reports" \\
      $IMAGE report --runs {run_args} \\
      --variants variants/generated.jsonl variants/paraphrase.jsonl --out reports/frozen.html

Gates: jev, rules, judge-claude, gpt-6-luna-decisions, pplx-decider, drex, judge-gemma. P variants
(--variants variants/paraphrase.jsonl) replay the same way. BUNDLE.json lists the
frozen inputs' sha256; the image ships those inputs.
"""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect(root: Path = ROOT, runs: tuple[str, ...] = FROZEN) -> dict[str, bytes]:
    """bundle-relative path -> bytes, for the runs, their batch logs and the cache entries they use."""
    files: dict[str, bytes] = {}
    keys: set[str] = set()
    for run in runs:
        data = (root / "runs" / f"{run}.jsonl").read_bytes()
        files[f"runs/{run}.jsonl"] = data
        batches = root / "runs" / f"{run}.batches.json"
        if batches.exists():
            files[f"runs/{run}.batches.json"] = batches.read_bytes()
        for line in data.decode("utf-8").splitlines():
            row = json.loads(line)
            if row["status"] in ("ok", "refusal"):  # an error or not_applicable row has no answer
                keys.add(row["cache_key"])
    missing = sorted(k for k in keys if not (root / "cache" / f"{k}.json").exists())
    if missing:
        raise SystemExit(
            f"{len(missing)} cache entries behind the frozen runs are missing, e.g. {missing[0]}"
        )
    for k in sorted(keys):
        files[f"cache/{k}.json"] = (root / "cache" / f"{k}.json").read_bytes()
    return files


def describe(files: dict[str, bytes], name: str, root: Path, runs: tuple[str, ...], commit: str) -> dict:
    return {
        "bundle": name,
        "results_frozen_at": FREEZE,
        "built_from": commit,
        "gemma_runs_added_at": RESULTS,
        "results": "results/x2-seven-gates",
        "runs": list(runs),
        "rows": sum(files[f"runs/{r}.jsonl"].count(b"\n") for r in runs),
        "cache_entries": sum(1 for p in files if p.startswith("cache/")),
        "inputs_sha256": {p: _sha256((root / p).read_bytes()) for p in INPUTS},
    }


def archive(files: dict[str, bytes], name: str) -> bytes:
    """A deterministic .tar.gz: sorted paths, fixed mtime/owner/mode, gzip without a timestamp."""
    raw = io.BytesIO()
    with (
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar,
    ):
        for path in sorted(files):
            info = tarfile.TarInfo(f"{name}/{path}")
            info.size, info.mtime, info.mode = len(files[path]), 0, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(files[path]))
    return raw.getvalue()


def build(out: Path, root: Path = ROOT, runs: tuple[str, ...] = FROZEN, commit: str = "") -> Path:
    name = f"gateprobe-replay-{RESULTS}"
    files = collect(root, runs)
    run_args = " ".join(f"runs/{r}.jsonl" for r in sorted(runs))  # the order the page uses
    readme = README.format(name=name, freeze=FREEZE, results=RESULTS, run_args=run_args)
    files["README.md"] = readme.encode("utf-8")
    files["BUNDLE.json"] = (json.dumps(describe(files, name, root, runs, commit), indent=2) + "\n").encode()
    files["MANIFEST.sha256"] = "".join(f"{_sha256(files[p])}  {p}\n" for p in sorted(files)).encode()
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.tar.gz"
    data = archive(files, name)
    path.write_bytes(data)
    (out / f"{name}.tar.gz.sha256").write_text(f"{_sha256(data)}  {path.name}\n", encoding="utf-8")
    return path


def site(out: Path, root: Path = ROOT, runs: tuple[str, ...] = FROZEN) -> Path:
    from gateprobe import cli

    page = out / "site" / "index.html"
    code = cli.main(
        # sorted, as a shell glob lists them, so the README's command reproduces this page byte for byte
        ["report", "--runs", *(str(root / "runs" / f"{r}.jsonl") for r in sorted(runs))]
        + [
            "--variants",
            str(root / "variants" / "generated.jsonl"),
            str(root / "variants" / "paraphrase.jsonl"),
        ]
        + ["--out", str(page), "--title", "GateProbe: the frozen results (ICSE 2027 Tool Demo)"]
    )
    if code:
        raise SystemExit(f"gateprobe report exited {code}")
    (page.parent / ".nojekyll").write_text("", encoding="utf-8")
    return page


def main() -> int:
    from gateprobe.runner.run import git_hash

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--no-site", action="store_true", help="only the bundle")
    args = parser.parse_args()
    path = build(args.out, commit=git_hash())
    print(f"bundle: {path} ({path.stat().st_size / 1e6:.1f} MB)")
    if not args.no_site:
        print(f"site: {site(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
