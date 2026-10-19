"""The `gateprobe` command: expand, run, report, ci, replay.

Scope of v0: the command surface only — every subcommand has `--help`, and each
one not built yet exits with status 3 and names the plan step that builds it.
Out of scope: the subcommands' behavior (see the steps in `PLANNED`).
"""

from __future__ import annotations

import argparse
import sys

from gateprobe import __version__

NOT_IMPLEMENTED = 3

# subcommand -> (help text, plan step that implements it)
PLANNED: dict[str, tuple[str, str]] = {
    "expand": ("generate relation variants from the probe corpus", "C4/C5"),
    "run": ("send variants x repeats through a gate", "R2"),
    "report": ("render a run as a single-file HTML report", "I1"),
    "ci": ("fail when a relation's flip rate exceeds --max-flip", "I3"),
    "replay": ("re-run from the response cache, with no API key", "R2"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gateprobe", description="Metamorphic testing of coding-agent permission gates."
    )
    parser.add_argument("--version", action="version", version=f"gateprobe {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="{" + ",".join(PLANNED) + "}")
    for name, (help_text, step) in PLANNED.items():
        sub.add_parser(name, help=help_text, description=f"{help_text} (built in step {step}).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    step = PLANNED[args.command][1]
    print(
        f"gateprobe {args.command}: not implemented yet — step {step} in docs/PLAN.md builds it",
        file=sys.stderr,
    )
    return NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main())
