"""Tests for the public release tree (scripts/make_release.py, I6). Dev-only: not shipped in it.

Scope of v0: what is kept and left out; every redaction still matches the development files
exactly once and changes no parsed config; the scan catches each forbidden category and env
files; the real tree builds and scans clean; the orphan commit holds exactly the built files.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mr():
    spec = importlib.util.spec_from_file_location("make_release", ROOT / "scripts" / "make_release.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selection_keeps_the_reproduction_files_and_drops_the_pipeline():
    mr = _mr()
    kept = [
        "src/gateprobe/cli.py",
        "scripts/build_bundle.py",
        "docs/RELATIONS.md",
        "docs/experiments/x4-final-results.md",
        "results/x4-final/relations.csv",
        "integrations/hf-space/data.json",
        "Dockerfile",
        "action.yml",
    ]
    dropped = [
        ".claude/commands/continue.md",
        "memory/README.md",
        "docs/PLAN.md",
        "docs/AUTONOMY.md",
        "docs/gates/g3-results-freeze.md",
        "docs/experiments/README.md",
        "STATUS.md",
        "CLAUDE.md",
        "gateprobe_plan.md",
        "paper/main.tex",
        "video/storyboard.md",
        "scripts/claim.py",
        "scripts/make_release.py",
        "tests/test_claim.py",
        "tests/test_release.py",
        "release/README.md",
        ".env.example",
    ]
    assert mr.selected(kept + dropped) == sorted(kept)


def test_every_redaction_matches_once_and_keeps_the_parsed_config(tmp_path):
    mr = _mr()
    for path, subs in mr.REDACTIONS.items():
        text = mr.redact(path, (ROOT / path).read_text(encoding="utf-8"))
        assert all(old not in text and new in text for old, new in subs), path
    with pytest.raises(SystemExit, match="matches 0 times"):
        mr.redact("configs/gates.yaml", "no such comment")
    redacted = tmp_path / "gates.yaml"
    redacted.write_text(mr.redact("configs/gates.yaml", (ROOT / "configs/gates.yaml").read_text()))
    assert mr.same_config(ROOT / "configs" / "gates.yaml", redacted)
    redacted.write_text(
        redacted.read_text().replace("typesafe/jev-1.14-20261014", "typesafe/jev-1.14-20261015")
    )
    assert not mr.same_config(ROOT / "configs" / "gates.yaml", redacted)


@pytest.mark.parametrize(
    "line,category",
    [
        ("key = sk-or-v1-" + "0" * 64, "OpenRouter key"),
        ("token hf_" + "A" * 34, "Hugging Face token"),
        ("ssh d.dgx", "internal host"),
        ("on gpubox", "internal host"),
        ("mount /data/storage/x", "storage path"),
        ("open /Users/someone/x", "storage path"),
        ("host 10.64.8.12", "private IP"),
        ("by agent@laptop.local", "local identity"),
        ("cite the Authority paper", "unpublished prior work"),
        ("see CLAUDE.md", "planning record"),
    ],
)
def test_scan_catches_each_category(tmp_path, line, category):
    mr = _mr()
    (tmp_path / "f.txt").write_text(f"fine\n{line}\n")
    rules = mr.WARN if category == "planning record" else mr.SCAN
    assert mr.scan(tmp_path, rules) == [f"f.txt:2: {category}"]


def test_scan_flags_env_files_and_passes_fakes_and_synthetic_paths(tmp_path):
    mr = _mr()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / ".env.local").write_text("X=1\n")
    (tmp_path / "ok.py").write_text('KEY = "sk-or-test-not-a-real-key"\nHOME = "/home/agent"\n')
    assert mr.scan(tmp_path) == ["sub/.env.local: an env file"]


def test_the_real_tree_builds_and_scans_clean(tmp_path):
    mr = _mr()
    files = mr.build(tmp_path / "release")
    assert "README.md" in files and "src/gateprobe/cli.py" in files
    assert (tmp_path / "release" / "README.md").read_text() == (ROOT / "release" / "README.md").read_text()
    assert mr.scan(tmp_path / "release") == []


def test_orphan_commit_holds_exactly_the_built_files(tmp_path):
    mr = _mr()
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout

    git("init", "-q")
    git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "--allow-empty", "-m", "dev")
    tree = tmp_path / "tree"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "a.py").write_text("a\n")
    (tree / ".venv").mkdir()
    (tree / ".venv" / "junk").write_text("not built\n")
    commit = mr.commit_branch(tree, ["src/a.py"], "release", root=repo)
    assert git("ls-tree", "-r", "--name-only", "release").split() == ["src/a.py"]
    assert git("rev-list", "--count", "release").strip() == "1" and commit
    assert git("status", "--porcelain") == ""
