#!/usr/bin/env python3
"""Atomically claim the next eligible plan step (see docs/AUTONOMY.md).

Optimistic lock with git as the arbiter: edit docs/PLAN.md to mark the first
eligible `todo` step as `claimed`, commit, and push to main. If the push is
rejected (another agent claimed concurrently and pushed first), hard-reset to
origin/main — discarding our local claim — and re-pick. Whoever's push lands
first owns the step; everyone else re-picks the next one.

Usage:
    scripts/claim.py [--dry-run] [--lane C[,R...]] [--skip-tag TAG]...

`--dry-run` prints the step that WOULD be claimed (id + block) without touching
git — use it to check hardware/API requirements before actually claiming.
`--lane` keeps only steps whose id starts with one of the given lane letters
(C corpus/relations, R runner/analysis, X runs, I integrations, W paper/video);
the shared lanes S (skeleton) and G (decision packets) pass every lane filter,
so a lane agent never idles on shared work. `--skip-tag` skips steps whose title carries
that tag (e.g. `--skip-tag GPU` on a machine that can't reach the H100);
repeatable or comma-separated.

Steps tagged `[HUMAN]` are never claimed: a human does them and runs
`mark.py <id> done`. They are listed as "waiting on a human" instead. A
dependency counts as met when it is `done` or `cut` (retired by a human).

Run this only on a clean `main`. Prints `CLAIMED <id>` then the step block on
success. Exit codes: 0 claimed (or dry-run found a step), 2 bad usage or dirty
tree, 3 nothing eligible, 4 retries exhausted.
"""

from __future__ import annotations

import datetime
import re
import socket
import subprocess
import sys
from pathlib import Path

PLAN = "docs/PLAN.md"
RETRIES = 8
HEADER = re.compile(r"^### +(\S+)\b(.*)$")
FIELD = re.compile(r"^- (status|owner|claimed_at|deps|source|done-when):\s*(.*)$")
TAG = re.compile(r"\[([A-Z]+)(?::[^\]]*)?\]")
LANE = re.compile(r"^[A-Za-z]+")
RESOLVED = {"done", "cut"}
NEVER_CLAIM = {"HUMAN"}
SHARED_LANES = {"S", "G"}
USAGE = "usage: claim.py [--dry-run] [--lane C[,R...]] [--skip-tag TAG]..."


def git(*args, check=True):
    r = subprocess.run(["git", *args], text=True, capture_output=True)
    if check and r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"git {' '.join(args)} failed")
    return r


def agent_id() -> str:
    name = (
        subprocess.run(["git", "config", "user.name"], text=True, capture_output=True).stdout.strip()
        or "unknown"
    )
    name = re.sub(r"[^A-Za-z0-9_-]", "-", name)
    return f"{name}@{socket.gethostname()}"


def parse(lines: list[str]) -> list[dict]:
    blocks: list[dict] = []
    cur: dict | None = None
    in_fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADER.match(line)
        if m:
            title = re.sub(r"^[—–-]+\s*", "", m.group(2).strip())
            cur = {"id": m.group(1), "title": title, "fields": {}, "start": i}
            blocks.append(cur)
        elif cur is not None:
            fm = FIELD.match(line)
            if fm:
                cur["fields"][fm.group(1)] = (i, fm.group(2).strip())
    return blocks


def status_of(b: dict) -> str | None:
    f = b["fields"].get("status")
    return f[1] if f else None


def base_status(b: dict) -> str | None:
    """The status word without a trailing note, e.g. `in_review (#12)` -> `in_review`."""
    s = status_of(b)
    return re.split(r"[\s(]", s, maxsplit=1)[0] if s else None


def deps_of(b: dict) -> list[str]:
    f = b["fields"].get("deps")
    if not f:
        return []
    return [d for d in re.split(r"[,\s]+", f[1]) if d and d not in ("—", "-")]


def tags_of(b: dict) -> set[str]:
    return set(TAG.findall(b["title"]))


def lane_of(b: dict) -> str:
    m = LANE.match(b["id"])
    return m.group(0).upper() if m else ""


def eligible(blocks: list[dict]) -> list[dict]:
    """Every `todo` step whose deps are all resolved, in file order (HUMAN steps included)."""
    resolved = {b["id"] for b in blocks if base_status(b) in RESOLVED}
    return [b for b in blocks if base_status(b) == "todo" and all(d in resolved for d in deps_of(b))]


def pick(blocks: list[dict], lanes: set[str] | None = None, skip_tags: set[str] | None = None) -> dict | None:
    for b in eligible(blocks):
        tags = tags_of(b)
        if tags & NEVER_CLAIM or tags & (skip_tags or set()):
            continue
        if lanes and lane_of(b) not in lanes | SHARED_LANES:
            continue
        return b
    return None


def waiting_on_human(blocks: list[dict]) -> list[dict]:
    return [b for b in eligible(blocks) if tags_of(b) & NEVER_CLAIM]


def block_text(lines: list[str], blocks: list[dict], b: dict) -> str:
    start = b["start"]
    end = len(lines)
    for nb in blocks:
        if nb["start"] > start:
            end = nb["start"]
            break
    return "\n".join(lines[start:end]).strip()


def parse_args(argv: list[str]) -> dict | None:
    """Return the options, or None on anything unexpected (never fall through to a real claim)."""
    opts: dict = {"dry": False, "lanes": set(), "skip": set()}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            opts["dry"] = True
        elif a in ("--lane", "--skip-tag"):
            if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
                return None
            vals = {v.strip().upper() for v in argv[i + 1].split(",") if v.strip()}
            if not vals:
                return None
            opts["lanes" if a == "--lane" else "skip"] |= vals
            i += 1
        else:
            return None
        i += 1
    return opts


def print_waiting(blocks: list[dict]) -> None:
    for b in waiting_on_human(blocks):
        print(f"waiting on a human: {b['id']} — {b['title']}")


def dirty_tracked_files() -> list[str]:
    """Tracked files with uncommitted changes (the hard reset below would discard them)."""
    out = git("status", "--porcelain", "--untracked-files=no", check=False).stdout
    return [line[3:] for line in out.splitlines() if line.strip()]


def main() -> int:
    opts = parse_args(sys.argv[1:])
    if opts is None:
        # Any other argument (e.g. --help) must never fall through to a REAL claim + hard reset.
        print(__doc__)
        print(f"unexpected arguments {sys.argv[1:]!r}; {USAGE}", file=sys.stderr)
        return 2
    aid = agent_id()
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if opts["dry"]:
        lines = Path(PLAN).read_text(encoding="utf-8").splitlines()
        blocks = parse(lines)
        b = pick(blocks, opts["lanes"], opts["skip"])
        if b is None:
            print("NONE — no eligible todo step (all done, claimed, blocked by deps, or filtered out)")
            print_waiting(blocks)
            return 3
        print(f"WOULD CLAIM {b['id']}")
        print(block_text(lines, blocks, b))
        print_waiting(blocks)
        return 0
    dirty = dirty_tracked_files()
    if dirty:
        print(f"refusing to claim: uncommitted changes would be lost by the reset: {dirty}", file=sys.stderr)
        return 2
    git("checkout", "main", check=False)
    for _ in range(RETRIES):
        git("fetch", "origin", "main")
        git("reset", "--hard", "origin/main")
        lines = Path(PLAN).read_text(encoding="utf-8").splitlines()
        blocks = parse(lines)
        b = pick(blocks, opts["lanes"], opts["skip"])
        if b is None:
            print("NONE — no eligible todo step (all done, claimed, blocked by deps, or filtered out)")
            print_waiting(blocks)
            return 3
        for name, val in (("status", "claimed"), ("owner", aid), ("claimed_at", ts)):
            if name in b["fields"]:
                idx, _ = b["fields"][name]
                lines[idx] = f"- {name}: {val}"
        Path(PLAN).write_text("\n".join(lines) + "\n", encoding="utf-8")
        git("add", PLAN)
        git("commit", "-m", f"chore(plan): claim {b['id']}")
        if git("push", "origin", "main", check=False).returncode == 0:
            print(f"CLAIMED {b['id']}")
            print(block_text(lines, blocks, b))
            return 0
        sys.stderr.write("push rejected — another agent won the race; re-syncing\n")
    print("retries exhausted")
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
