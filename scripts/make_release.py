#!/usr/bin/env python3
"""Build the public release tree: reproduction-only and identity-clean (I6).

Copies the tracked files of HEAD a reviewer needs: code, configs, corpus, policies, variants,
results, tests, the Dockerfile, the action, the integrations, the relation and corpus docs and
the run reports. It leaves out the agent pipeline and the planning records, applies the declared
redactions (each must match exactly once, so drift fails loudly), puts release/README.md in place
as the README, and scans every file for secrets, internal hosts, storage paths, private IPs,
local identities and the unpublished prior work. A hit fails the build.

    uv run python scripts/make_release.py [--out dist/release] [--branch release]

--branch commits the tree as one orphan commit on a local branch; this script never pushes.
Publishing is H5.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = (
    "src/",
    "tests/",
    "configs/",
    "probes/",
    "policies/",
    "variants/",
    "results/",
    "integrations/",
    "docs/RELATIONS.md",
    "docs/CORPUS.md",
    "docs/LABELING.md",
    "docs/PARAPHRASE.md",
    "docs/experiments/x",
    ".github/workflows/gate.yml",
    "Dockerfile",
    ".dockerignore",
    "action.yml",
    "pyproject.toml",
    ".gitignore",
    ".gitattributes",
)
SCRIPTS = (  # the data and reproduction scripts; the loop, paper and bootstrap scripts stay behind
    "build_bundle.py",
    "build_corpus.py",
    "case_studies.py",
    "check.sh",
    "compare_runs.py",
    "decisions_smoke.py",
    "extract_variants.py",
    "label_cli.py",
    "paraphrase.py",
    "render_policies.py",
    "sample_labels.py",
    "x6_sandbox.py",
    "x6/Dockerfile",
    "x6/fixture.sh",
    "x6/run.sh",
    "x6/snapshot.py",
)
EXCLUDE = (  # tests of what stays behind
    "tests/test_claim.py",
    "tests/test_paper.py",
    "tests/test_paper_tables.py",
    "tests/test_smoke.py",
    "tests/test_video.py",
    "tests/test_release.py",
)
REDACTIONS = {
    "configs/gates.yaml": [
        ("# R5 sets http://d.dgx:<port>/v1", "# R5 sets the judge server's /v1 URL"),
        ("(CLAUDE.md invariant 6: every model id is pinned", "(every model id is pinned"),
    ],
    "policies/README.md": [
        (
            "**Provenance.** The plan assumed these renderings could be reused from an\n"
            "earlier internal codebase (examined at commit `088d0ab`, 16 Oct 2026). They\n"
            "could not: its renderers serialize a Cedar-style principal/action/resource\n"
            "model for entity authorization, and none of them produces YAML or bullets.\n"
            "So no rendering was reused; all four come from `gateprobe/corpus/render.py`.\n"
            "That codebase is unpublished and is not cited (`CLAUDE.md` invariant 13).\n",
            # Proposed public wording; the humans decide it at H5 (docs/PLAN.md, I6).
            "**Provenance.** All four renderings are generated from the policy sources by\n"
            "`gateprobe/corpus/render.py`; none is reused from elsewhere.\n",
        ),
    ],
}
SCAN = {  # any hit fails the build (I6's done-when)
    "OpenRouter key": r"sk-or-v1-[0-9a-f]{64}",
    "Anthropic key": r"sk-ant-[A-Za-z0-9_-]{80,}",
    "Hugging Face token": r"\bhf_[A-Za-z0-9]{30,}",
    "GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{36}",
    "AWS key": r"\bAKIA[0-9A-Z]{16}\b",
    "internal host": r"\b[abd]\.dgx\b|gpubox|nsslab|h100-01|kaluzhnaya|jhub",
    "storage path": r"/data/storage|/var/dockerstorage|/Users/|/home/(danya|jerzy)\b",
    "private IP": r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b192\.168\.\d{1,3}\.\d{1,3}\b"
    r"|\b172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b",
    "local identity": r"jerzy-pro|jerzypro|@[a-z0-9-]+\.local\b",
    "unpublished prior work": r"authority|supersession",
}
WARN = {  # reported, not failing: a pointer to a planning file this tree leaves out
    "planning record": r"CLAUDE\.md|AUTONOMY\.md|docs/PLAN\.md|STATUS\.md|\bmemory/|gateprobe_plan\.md",
}


def selected(paths: list[str]) -> list[str]:
    keep = [p for p in paths if p.startswith(INCLUDE) or p in {f"scripts/{s}" for s in SCRIPTS}]
    return sorted(p for p in keep if p not in EXCLUDE)


def redact(path: str, text: str) -> str:
    for old, new in REDACTIONS.get(path, []):
        if text.count(old) != 1:
            raise SystemExit(f"redaction for {path} matches {text.count(old)} times; update REDACTIONS")
        text = text.replace(old, new)
    return text


def scan(tree: Path, rules: dict[str, str] = SCAN) -> list[str]:
    patterns = {name: re.compile(p, re.IGNORECASE) for name, p in rules.items()}
    hits = []
    for path in sorted(tree.rglob("*")):
        rel = path.relative_to(tree).as_posix()
        if path.is_dir():
            continue
        if re.search(r"(^|/)\.env(\.|$)", rel):
            hits.append(f"{rel}: an env file")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), start=1):
            hits += [f"{rel}:{n}: {name}" for name, p in patterns.items() if p.search(line)]
    return hits


def same_config(original: Path, redacted: Path) -> bool:
    from gateprobe.config import load_gates

    return load_gates(original) == load_gates(redacted)


def build(out: Path, root: Path = ROOT) -> list[str]:
    tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True)
    files = selected(tracked.stdout.splitlines())
    if out.exists():
        shutil.rmtree(out)
    for rel in files:
        src, dst = root / rel, out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel in REDACTIONS:
            dst.write_text(redact(rel, src.read_text(encoding="utf-8")), encoding="utf-8")
        else:
            shutil.copy2(src, dst)
    shutil.copy2(root / "release" / "README.md", out / "README.md")
    if not same_config(root / "configs" / "gates.yaml", out / "configs" / "gates.yaml"):
        raise SystemExit("the redacted configs/gates.yaml parses differently; a redaction changed config")
    return [*files, "README.md"]


def commit_branch(tree: Path, files: list[str], branch: str, root: Path = ROOT) -> str:
    """One orphan commit holding exactly `files` from the tree, on a local branch; the working copy
    is untouched."""
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True)
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}

        def git(*args: str) -> str:
            r = subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, text=True, check=True)
            return r.stdout.strip()

        for i in range(0, len(files), 200):  # exactly the built files, nothing else in the tree
            git("--work-tree", str(tree), "add", "-f", "--", *files[i : i + 200])
        tree_id = git("write-tree")
        msg = f"GateProbe release tree (from development commit {head.stdout.strip()})"
        commit = git("commit-tree", tree_id, "-m", msg)
        git("update-ref", f"refs/heads/{branch}", commit)
    return commit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "release")
    parser.add_argument("--branch", help="also commit the tree as an orphan commit on this local branch")
    args = parser.parse_args()
    files = build(args.out)
    hits, warnings = scan(args.out), scan(args.out, WARN)
    print(f"{len(files)} files -> {args.out}")
    if warnings:
        print(f"warnings: {len(warnings)}", *warnings, sep="\n  ")
    if hits:
        print(f"scan: {len(hits)} hits", *hits[:50], sep="\n  ")
        return 1
    print("scan: clean")
    if args.branch:
        commit = commit_branch(args.out, files, args.branch)
        print(f"branch {args.branch}: {commit} (local only; publishing is H5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
