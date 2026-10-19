#!/usr/bin/env python3
"""Set a plan step's status on main, atomically (see docs/AUTONOMY.md).

Usage:
    scripts/mark.py <step-id> <status> [note...]

<status> is written verbatim, so it may carry a PR ref, e.g.
    scripts/mark.py C2 "in_review (#12)"
    scripts/mark.py C2 done
    scripts/mark.py X1 blocked "Decisions API unreachable since 21:00; fallback is a human call"
    scripts/mark.py G1 blocked "awaiting human decision — docs/gates/g1-spec-freeze.md"
    scripts/mark.py X2 todo "needs the H100; this machine can't reach d.dgx"   # release a claim
    scripts/mark.py H1 done          # a human closing a [HUMAN] step or a [GATE] decision
    scripts/mark.py X6 cut "G2: reduced scope"   # human-only: retire a step

Its first word must be one of: todo, claimed, in_review, done, blocked, cut.

Same optimistic-lock loop as claim.py: fetch + hard-reset to origin/main, edit
the step's `- status:` line (and a `- note:` line when a note is given), commit,
push; retry on rejection. Run on a clean `main`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PLAN = "docs/PLAN.md"
RETRIES = 8
HEADER = re.compile(r"^### +(\S+)\b")
VALID = {"todo", "claimed", "in_review", "done", "blocked", "cut"}


def git(*args, check=True):
    r = subprocess.run(["git", *args], text=True, capture_output=True)
    if check and r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"git {' '.join(args)} failed")
    return r


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    step_id, status = sys.argv[1], sys.argv[2]
    note = " ".join(sys.argv[3:]).strip()
    if re.split(r"[\s(]", status, maxsplit=1)[0] not in VALID:
        print(f"refusing to mark: status {status!r} must start with one of {sorted(VALID)}", file=sys.stderr)
        return 2
    dirty = [
        line[3:]
        for line in git("status", "--porcelain", "--untracked-files=no", check=False).stdout.splitlines()
        if line.strip()
    ]
    if dirty:
        print(f"refusing to mark: uncommitted changes would be lost by the reset: {dirty}", file=sys.stderr)
        return 2

    git("checkout", "main", check=False)
    for _ in range(RETRIES):
        git("fetch", "origin", "main")
        git("reset", "--hard", "origin/main")
        lines = Path(PLAN).read_text(encoding="utf-8").splitlines()

        # locate the target block's line range
        start = None
        for i, line in enumerate(lines):
            m = HEADER.match(line)
            if m and m.group(1) == step_id:
                start = i
                break
        if start is None:
            print(f"step {step_id!r} not found in {PLAN}")
            return 3
        end = len(lines)
        for i in range(start + 1, len(lines)):
            if HEADER.match(lines[i]):
                end = i
                break

        status_idx = note_idx = None
        for i in range(start, end):
            if re.match(r"^- status:", lines[i]):
                status_idx = i
            elif re.match(r"^- note:", lines[i]):
                note_idx = i
        if status_idx is None:
            print(f"step {step_id!r} has no `- status:` line")
            return 3
        lines[status_idx] = f"- status: {status}"
        if note:
            if note_idx is not None:
                lines[note_idx] = f"- note: {note}"
            else:
                lines.insert(status_idx + 1, f"- note: {note}")

        Path(PLAN).write_text("\n".join(lines) + "\n", encoding="utf-8")
        git("add", PLAN)
        git("commit", "-m", f"chore(plan): mark {step_id} {status}")
        if git("push", "origin", "main", check=False).returncode == 0:
            print(f"MARKED {step_id} -> {status}")
            return 0
        sys.stderr.write("push rejected; re-syncing\n")
    print("retries exhausted")
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
