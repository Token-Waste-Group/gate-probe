"""Tests for the claim/mark scripts: step picking, lanes, tags, and git safety.

Scope of v0: the pure picking logic and the guards that must fire before any
git command runs. Out of scope: the push/retry race (it needs a real remote).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SAMPLE = """\
### S1 — skeleton
- status: done
- owner: a
- claimed_at: t
- deps: —
- source: s
- done-when: d

### H1 — accounts [HUMAN]
- status: todo
- owner: —
- claimed_at: —
- deps: —
- source: s
- done-when: d

### C1 — spec
- status: todo
- owner: —
- claimed_at: —
- deps: S1
- source: s
- done-when: d

### R1 — decisions adapter [API: OpenRouter]
- status: todo
- owner: —
- claimed_at: —
- deps: S1
- source: s
- done-when: d

### X6 — sandbox [STRETCH]
- status: cut
- owner: —
- claimed_at: —
- deps: S1
- source: s
- done-when: d

### W9 — after the cut stretch step
- status: todo
- owner: —
- claimed_at: —
- deps: X6
- source: s
- done-when: d

### C2 — after the spec
- status: todo
- owner: —
- claimed_at: —
- deps: C1
- source: s
- done-when: d
"""


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _blocks():
    claim = _load("claim")
    return claim, claim.parse(SAMPLE.splitlines())


def test_parse_reads_titles_and_tags():
    claim, blocks = _blocks()
    r1 = next(b for b in blocks if b["id"] == "R1")
    assert r1["title"] == "decisions adapter [API: OpenRouter]"
    assert claim.tags_of(r1) == {"API"}
    assert claim.lane_of(r1) == "R"


def test_human_steps_are_never_picked_but_are_reported():
    claim, blocks = _blocks()
    assert claim.pick(blocks)["id"] == "C1"  # H1 comes first in file order but is [HUMAN]
    assert [b["id"] for b in claim.waiting_on_human(blocks)] == ["H1"]
    assert claim.pick(blocks, lanes={"H"}) is None


def test_lane_filter():
    claim, blocks = _blocks()
    assert claim.pick(blocks, lanes={"R"})["id"] == "R1"
    assert claim.pick(blocks, lanes={"W", "R"})["id"] == "R1"
    assert claim.pick(blocks, lanes={"I"}) is None


def test_shared_lanes_pass_every_lane_filter():
    claim = _load("claim")
    shared = SAMPLE.replace("### S1 — skeleton\n- status: done", "### S1 — skeleton\n- status: todo")
    shared += "\n### G1 — freeze [GATE]\n- status: todo\n- owner: —\n- claimed_at: —\n- deps: —\n"
    shared += "- source: s\n- done-when: d\n"
    blocks = claim.parse(shared.splitlines())
    assert claim.pick(blocks, lanes={"C"})["id"] == "S1"
    assert claim.pick(blocks, lanes={"I"})["id"] == "S1"
    blocks = claim.parse(SAMPLE.splitlines() + shared.splitlines()[-7:])
    assert claim.pick(blocks, lanes={"I"})["id"] == "G1"


def test_skip_tag():
    claim, blocks = _blocks()
    assert claim.pick(blocks, lanes={"R"}, skip_tags={"API"}) is None


def test_cut_dependency_counts_as_met():
    claim, blocks = _blocks()
    assert claim.pick(blocks, lanes={"W"})["id"] == "W9"


def test_unresolved_dependency_blocks():
    claim, blocks = _blocks()
    assert "C2" not in {b["id"] for b in claim.eligible(blocks)}  # C1 is still todo


def test_parse_args():
    claim = _load("claim")
    assert claim.parse_args([]) == {"dry": False, "lanes": set(), "skip": set()}
    opts = claim.parse_args(["--dry-run", "--lane", "c,r", "--skip-tag", "GPU", "--skip-tag", "api"])
    assert opts == {"dry": True, "lanes": {"C", "R"}, "skip": {"GPU", "API"}}
    assert claim.parse_args(["--help"]) is None
    assert claim.parse_args(["--lane"]) is None
    assert claim.parse_args(["--lane", "--dry-run"]) is None


def test_claim_rejects_unknown_args_before_touching_git(monkeypatch):
    # an unknown flag (e.g. --help) must never fall through to a real claim and a hard reset
    claim = _load("claim")

    def no_git(*a, **k):
        raise AssertionError("git must not be called")

    monkeypatch.setattr(claim, "git", no_git)
    monkeypatch.setattr(sys, "argv", ["claim.py", "--help"])
    assert claim.main() == 2


def test_claim_refuses_with_dirty_tracked_files(monkeypatch):
    claim = _load("claim")
    calls = []

    class R:
        stdout = " M docs/PLAN.md\n"

    def fake_git(*a, **k):
        calls.append(a)
        if a[0] == "status":
            return R()
        raise AssertionError(f"reset/checkout must not run: {a}")

    monkeypatch.setattr(claim, "git", fake_git)
    monkeypatch.setattr(sys, "argv", ["claim.py"])
    assert claim.main() == 2
    assert calls == [("status", "--porcelain", "--untracked-files=no")]


def test_mark_rejects_unknown_status_before_touching_git(monkeypatch):
    mark = _load("mark")

    def no_git(*a, **k):
        raise AssertionError("git must not be called")

    monkeypatch.setattr(mark, "git", no_git)
    monkeypatch.setattr(sys, "argv", ["mark.py", "C1", "dnoe"])
    assert mark.main() == 2
