"""Equivalence (E) generators: rewrites that must not change the verdict (docs/RELATIONS.md § 2).

Meaning is preserved by construction: every flag swap comes from FLAGS (an
explicit per-command table of short and long forms, each entry unit-tested),
operand reordering only touches commands in SET_OPERANDS, quoting never
touches an operand where quotes change meaning (`~`, `$`, globs), and path
rewrites rely on every call running in the project root. Token rewrites
apply to simple commands only (no pipes, chains, redirects); the rest are
counted as skips.

Scope of v0: the seven E transforms. Out of scope: anything not in the catalog.
"""

from __future__ import annotations

import random
import re
from typing import Any

from gateprobe.corpus.schema import RENDERINGS, Probe
from gateprobe.relations.common import Change, Tokens, is_simple, program_of, with_command

# (program, subcommand) -> {short flag letter: long flag}. Subcommand "" = the bare program.
FLAGS: dict[tuple[str, str], dict[str, str]] = {
    ("rm", ""): {"r": "--recursive", "f": "--force"},
    ("cp", ""): {"r": "--recursive"},
    ("ls", ""): {"a": "--all"},
    ("grep", ""): {"r": "--recursive", "n": "--line-number"},
    ("chmod", ""): {"R": "--recursive"},
    ("make", ""): {"n": "--dry-run"},
    ("curl", ""): {
        "s": "--silent",
        "I": "--head",
        "f": "--fail",
        "S": "--show-error",
        "L": "--location",
        "o": "--output",
        "X": "--request",
        "F": "--form",
        "T": "--upload-file",
    },
    ("wget", ""): {"q": "--quiet", "O": "--output-document"},
    ("rsync", ""): {"a": "--archive", "z": "--compress", "n": "--dry-run"},
    ("git", "push"): {"u": "--set-upstream", "f": "--force"},
    ("git", "commit"): {"m": "--message"},
    ("git", "clean"): {"f": "--force", "n": "--dry-run"},
    ("git", "branch"): {"a": "--all"},
    ("pip", "install"): {"r": "--requirement", "U": "--upgrade", "e": "--editable"},
    ("pip", "uninstall"): {"y": "--yes"},
    ("npm", "install"): {"g": "--global"},
    ("apt-get", "install"): {"y": "--yes"},
    ("apt-get", "remove"): {"y": "--yes"},
}
# Short flags that take a value (`-o file`, `-m msg`, attached `-O-`): never reordered.
VALUE_FLAGS: dict[tuple[str, str], set[str]] = {
    ("curl", ""): {"o", "X", "F", "T"},
    ("wget", ""): {"O"},
    ("git", "commit"): {"m"},
    ("pip", "install"): {"r", "e"},
}
# Commands whose operands are a set: their order never changes the effect.
SET_OPERANDS = {
    ("rm", ""),
    ("chmod", ""),
    ("git", "add"),
    ("git", "rm"),
    ("pip", "install"),
    ("pip", "uninstall"),
    ("npm", "install"),
    ("touch", ""),
}
# Directories in the corpus, where a trailing slash is equivalent.
DIRECTORIES = {
    "build",
    "dist",
    ".cache",
    "node_modules",
    "coverage",
    "src",
    "tests",
    "scripts",
    ".git",
    "config",
    "backup",
}
MULTI_COMMAND = {"git", "npm", "pip", "cargo", "apt-get", "uv", "brew"}  # programs with subcommands
PLAIN = re.compile(r"^[A-Za-z0-9._/@:=+,-]+$")  # quoting it is a no-op for the shell


def _key(tokens: list[str]) -> tuple[int, tuple[str, str]]:
    i, prog, sub = program_of(tokens)
    if (prog, sub) in FLAGS or (prog, sub) in SET_OPERANDS:
        return i, (prog, sub)
    return i, (prog, "")


def flag_long_short(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """Swap every flag of the command that has a known short/long pair, in one direction."""
    cmd = probe.call.get("command")
    if probe.tool != "Bash" or not cmd or not is_simple(cmd):
        return []
    t = Tokens.split(cmd)
    _, key = _key(t.raw)
    table = FLAGS.get(key)
    if not table:
        return []
    reverse = {long: short for short, long in table.items()}
    changed = False
    for idx, tok in enumerate(t.raw):
        if tok in reverse:  # long -> short
            t.raw[idx] = "-" + reverse[tok]
            changed = True
        elif re.fullmatch(r"-[A-Za-z]+.*", tok) and not tok.startswith("--"):
            letters, rest = tok[1:], ""
            longs = []
            for j, ch in enumerate(letters):
                if ch not in table:
                    longs = []
                    break
                longs.append(table[ch])
                if ch in VALUE_FLAGS.get(key, set()):
                    rest = letters[j + 1 :]
                    break
            if longs:
                if rest:  # an attached value: -O- -> --output-document=-
                    longs[-1] = f"{longs[-1]}={rest}"
                t.raw[idx] = " ".join(longs)
                changed = True
    return [with_command(probe, t.join())] if changed else []


def flag_order(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """Reorder value-less flags: letters inside a bundle, or whole flag tokens among their positions."""
    cmd = probe.call.get("command")
    if probe.tool != "Bash" or not cmd or not is_simple(cmd):
        return []
    t = Tokens.split(cmd)
    _, key = _key(t.raw)
    if key not in FLAGS:
        return []
    values = VALUE_FLAGS.get(key, set())
    value_longs = {FLAGS[key][v] for v in values if v in FLAGS[key]}
    known_longs = set(FLAGS[key].values()) - value_longs

    def movable(i: int, tok: str) -> bool:
        if t.quoted[i] or "=" in tok or len(tok) < 2 or not tok.startswith("-"):
            return False
        if tok.startswith("--"):
            return tok in known_longs  # an unknown long flag might take the next token as its value
        return not set(tok[1:]) & values

    flag_pos = [i for i, tok in enumerate(t.raw) if movable(i, tok)]
    if len(flag_pos) >= 2:
        order = flag_pos[:]
        while order == flag_pos:
            rng.shuffle(order)
        new = list(t.raw)
        for dst, src in zip(flag_pos, order, strict=True):
            new[dst] = t.raw[src]
        t.raw = new
        return [with_command(probe, t.join())]
    for i in flag_pos:  # a single bundle like -rf / -la / -fdx
        tok = t.raw[i]
        if not tok.startswith("--") and len(tok) > 2:
            letters = list(tok[1:])
            while "".join(letters) == tok[1:]:
                rng.shuffle(letters)
            t.raw[i] = "-" + "".join(letters)
            return [with_command(probe, t.join())]
    return []


def operand_order(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """Reorder the operands of a command whose operands are a set (rm a b <-> rm b a)."""
    cmd = probe.call.get("command")
    if probe.tool != "Bash" or not cmd or not is_simple(cmd):
        return []
    t = Tokens.split(cmd)
    i, key = _key(t.raw)
    if key not in SET_OPERANDS:
        return []
    start = i + (2 if key[1] else 1)
    ops = [j for j in range(start, len(t.raw)) if not t.raw[j].startswith("-")]
    if key == ("chmod", ""):
        ops = ops[1:]  # the first operand is the mode, not a target
    if len(ops) < 2:
        return []
    order = ops[:]
    while order == ops:
        rng.shuffle(order)
    new = list(t.raw)
    for dst, src in zip(ops, order, strict=True):
        new[dst] = t.raw[src]
    t.raw = new
    return [with_command(probe, t.join())]


def quoting_whitespace(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """Two variants: single-quote one plain operand; widen the whitespace between tokens."""
    cmd = probe.call.get("command")
    if probe.tool != "Bash" or not cmd:
        return []
    out: list[Change] = []
    t = Tokens.split(cmd)
    if is_simple(cmd):
        i, prog, sub = program_of(t.raw)
        first = i + (2 if sub and prog in MULTI_COMMAND else 1)  # an argument, never the program/subcommand
        plain = [
            j
            for j in range(first, len(t.raw))
            if not t.raw[j].startswith("-") and PLAIN.fullmatch(t.raw[j]) and not t.quoted[j]
        ]
        if plain:
            j = rng.choice(plain)
            q = Tokens(raw=list(t.raw), seps=list(t.seps), trailing=t.trailing, quoted=list(t.quoted))
            q.raw[j] = f"'{q.raw[j]}'"
            out.append(with_command(probe, q.join()))
    if len(t.raw) >= 2:
        w = Tokens(
            raw=list(t.raw),
            seps=[t.seps[0]] + [s + " " * rng.randint(1, 3) for s in t.seps[1:]],
            trailing=t.trailing,
            quoted=list(t.quoted),
        )
        out.append(with_command(probe, w.join()))
    return out


def _looks_like_path(tok: str) -> bool:
    bare = tok.removeprefix("./").rstrip("/")
    return (
        tok.startswith("./")
        or "/" in bare
        or bare in DIRECTORIES
        or bool(re.search(r"\.[A-Za-z0-9]+$", bare))
    )


def _equivalent_paths(path: str, rng: random.Random, shell: bool) -> str | None:
    """Another spelling of the same relative path. `$PWD/x` and `dir/` only in the shell:
    the file tools take literal file paths."""
    if path.startswith(("~", "/", "$", "-")) or not PLAIN.fullmatch(path) or not _looks_like_path(path):
        return None
    bare = path.removeprefix("./").rstrip("/")
    if not bare or bare == ".":
        return None
    forms = {f"./{bare}", bare}
    if shell:
        forms.add(f"$PWD/{bare}")
        if bare in DIRECTORIES:
            forms.add(f"{bare}/")
    forms.discard(path)
    return rng.choice(sorted(forms)) if forms else None


def path_normalization(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """Rewrite one relative path in an equivalent form (./build, build, build/, $PWD/build)."""
    if probe.tool in ("Read", "Write", "Edit"):
        new = _equivalent_paths(str(probe.call.get("file_path", "")), rng, shell=False)
        return [{"call": {**probe.call, "file_path": new}}] if new else []
    cmd = probe.call.get("command")
    if probe.tool != "Bash" or not cmd or not is_simple(cmd):
        return []
    t = Tokens.split(cmd)
    i, prog, _ = program_of(t.raw)
    if prog in ("git", "pip", "npm", "cargo", "uv", "brew", "apt-get", "curl", "wget", "ssh", "scp", "make"):
        return []  # operands there are refs, packages, targets or hosts, not paths
    cands = [
        (j, form)
        for j in range(i + 1, len(t.raw))
        if not t.quoted[j] and (form := _equivalent_paths(t.raw[j], rng, shell=True)) is not None
    ]
    if not cands:
        return []
    j, form = rng.choice(cands)
    t.raw[j] = form
    return [with_command(probe, t.join())]


def json_key_order(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """Reverse the order of the tool-call argument keys (tools with two or more arguments)."""
    if len(probe.call) < 2:
        return []
    return [{"call": dict(reversed(list(probe.call.items())))}]


def policy_format(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """The same policy in each non-canonical rendering (three variants)."""
    return [{"policy_rendering": r} for r in RENDERINGS if r != "yaml"]


GENERATORS = {
    "flag_long_short": flag_long_short,
    "flag_order": flag_order,
    "operand_order": operand_order,
    "quoting_whitespace": quoting_whitespace,
    "path_normalization": path_normalization,
    "json_key_order": json_key_order,
    "policy_format": policy_format,
}
