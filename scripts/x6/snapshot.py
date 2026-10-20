"""Print the effect signature of the command that just ran (X6): exit status, the files under the
observed roots, the git state, and the files it opened under those roots. docker diff is taken
outside."""

import hashlib
import json
import os
import re
import subprocess

ROOTS = ("/work", "/home/agent", "/var/log/app")
OPENED = re.compile(r"= \d+<(/[^>]*)>")


def files() -> dict[str, str]:
    out = {}
    for root in ROOTS:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            if dirpath == "/work":
                dirnames[:] = [d for d in dirnames if d != ".git"]
            for name in sorted(dirnames) + sorted(filenames):
                p = os.path.join(dirpath, name)
                st = os.lstat(p)
                mode = oct(st.st_mode & 0o7777)
                if os.path.islink(p):
                    out[p] = f"link {os.readlink(p)}"
                elif os.path.isdir(p):
                    out[p] = f"dir {mode}"
                else:
                    try:
                        with open(p, "rb") as f:
                            digest = hashlib.sha256(f.read()).hexdigest()
                    except OSError as e:
                        digest = f"unreadable {e.errno}"
                    out[p] = f"file {mode} {digest}"
        if not os.path.exists(root):
            out[root] = "missing"
    return out


def git(*args: str, cwd: str = "/work") -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else f"error {r.returncode}"


def git_state() -> dict[str, str]:
    if not os.path.isdir("/work/.git"):
        return {"repo": "missing"}
    return {
        "head": git("symbolic-ref", "-q", "HEAD") or git("rev-parse", "HEAD"),
        "head_commit": git("rev-parse", "HEAD"),
        "refs": git("for-each-ref", "--format=%(refname) %(objectname)"),
        "index": git("ls-files", "-s"),
        "stash": git("stash", "list", "--format=%H"),
        "origin_refs": git("for-each-ref", "--format=%(refname) %(objectname)", cwd="/remote/origin.git"),
    }


def opened() -> list[str]:
    paths = set()
    try:
        with open("/tmp/x6.trace", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = OPENED.search(line)
                if not m:
                    continue
                p = m.group(1)
                if p.startswith(ROOTS) and "/.git/" not in p + "/" and not p.startswith("/work/.git"):
                    paths.add(p)
    except FileNotFoundError:
        pass
    return sorted(paths)


with open("/tmp/x6.status") as f:
    status = int(f.read().strip() or 0)
snapshot = {"status": status, "files": files(), "git": git_state(), "opened": opened()}
print(json.dumps(snapshot, sort_keys=True))
