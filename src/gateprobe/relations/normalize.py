"""A canonical form of a tool call, under which E-equivalent spellings coincide.

Used by the corpus build to guarantee that no two probes are the same call
(C6): quotes and extra whitespace are dropped, `./x`, `x` and `x/` become `x`,
short-flag bundles are split and sorted, and long flags with a known short
form (the E-class FLAGS table) become that short form. File-tool paths get the
same path rule; JSON argument order is ignored.

Scope of v0: what the E transforms can produce, so the corpus never contains
two probes that are E variants of each other. Out of scope: shell semantics
beyond that (aliases, globs, `$PWD`).
"""

from __future__ import annotations

import json
from typing import Any

from gateprobe.relations.common import Tokens, program_of
from gateprobe.relations.equivalence import FLAGS


def _path(tok: str) -> str:
    out = tok.removeprefix("./").rstrip("/")
    return out or "."


def normalize(tool: str, call: dict[str, Any]) -> str:
    if tool != "Bash" or "command" not in call:
        args = dict(call)
        if "file_path" in args:
            args["file_path"] = _path(str(args["file_path"]))
        return json.dumps([tool, args], sort_keys=True)
    raw = [t.replace("'", "").replace('"', "") for t in Tokens.split(str(call["command"])).raw]
    _, prog, sub = program_of(raw)
    table = FLAGS.get((prog, sub)) or FLAGS.get((prog, "")) or {}
    reverse = {long: short for short, long in table.items()}
    out: list[str] = []
    flags: list[str] = []
    for tok in raw:
        if tok in reverse:
            flags.append(reverse[tok])
        elif tok.startswith("-") and not tok.startswith("--") and len(tok) > 1 and tok[1:].isalpha():
            flags.extend(tok[1:])
        else:
            if flags:
                out.append("-" + "".join(sorted(flags)))
                flags = []
            out.append(_path(tok))
    if flags:
        out.append("-" + "".join(sorted(flags)))
    return json.dumps(["Bash", " ".join(out)])
