#!/usr/bin/env python3
"""Lint paper/ against the CFP's hard format rules and the repo's paper conventions.

Rules (docs/icse27-demo-cfp.md, CLAUDE.md § Paper):
- main.tex uses exactly `\\documentclass[10pt,conference]{IEEEtran}`; no compsoc anywhere;
- nothing alters spacing, margins or font sizes (geometry, \\linespread, negative \\vspace, ...);
- one section per file: main.tex has no \\section and only \\input's sections/*.tex; every
  sections/ file is input exactly once; abstract.tex has no section, every other file exactly one;
- every \\cite key exists in references.bib;
- with --final, no \\todo{...} is left anywhere (the macro's definition in main.tex aside), and no
  \\url{...} still holds a TODO placeholder (the tool and video links in main.tex).

Usage: scripts/check_paper.py [--final]   (exit 0 clean, 1 problems found, 2 bad usage)
Page count is checked by scripts/build_paper.sh after the build, not here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1] / "paper"
DOCCLASS = r"\documentclass[10pt,conference]{IEEEtran}"
# Patterns that change spacing, margins or font size. Matched on comment-stripped text.
FORBIDDEN = {
    "compsoc option": re.compile(r"compsoc"),
    "geometry package": re.compile(r"\\usepackage(\[[^\]]*\])?\{[^}]*\bgeometry\b"),
    "titlesec/savetrees/fullpage": re.compile(
        r"\\usepackage(\[[^\]]*\])?\{[^}]*\b(titlesec|savetrees|fullpage)\b"
    ),
    "\\linespread": re.compile(r"\\linespread"),
    "\\baselinestretch": re.compile(r"\\baselinestretch"),
    "negative \\vspace": re.compile(r"\\vspace\*?\{\s*-"),
    "\\enlargethispage": re.compile(r"\\enlargethispage"),
    "\\fontsize": re.compile(r"\\fontsize"),
    "layout length change": re.compile(
        r"\\(setlength|addtolength)\{?\\(textheight|textwidth|columnsep|topmargin|oddsidemargin|"
        r"evensidemargin|headsep|headheight|footskip|parskip|baselineskip|abovecaptionskip|"
        r"belowcaptionskip|textfloatsep|floatsep|intextsep|dbltextfloatsep|abovedisplayskip|"
        r"belowdisplayskip)\b"
    ),
}
INPUT = re.compile(r"\\(?:input|include)\{([^}]+)\}")
SECTION = re.compile(r"\\section\*?\{")
CITE = re.compile(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")
BIBKEY = re.compile(r"^\s*@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)
TODO = re.compile(r"\\todo\{")
PLACEHOLDER_URL = re.compile(r"\\url\{[^}]*TODO[^}]*\}")


def strip_comments(tex: str) -> str:
    """Drop TeX comments (an unescaped % to end of line)."""
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in tex.splitlines())


def check(paper: Path = PAPER, final: bool = False) -> list[str]:
    problems: list[str] = []
    main_path = paper / "main.tex"
    if not main_path.exists():
        return [f"{main_path} is missing"]
    main = strip_comments(main_path.read_text(encoding="utf-8"))

    classes = re.findall(r"\\documentclass(?:\[[^\]]*\])?\{[^}]*\}", main)
    if classes != [DOCCLASS]:
        problems.append(f"main.tex: expected exactly {DOCCLASS}, found {classes}")
    if SECTION.search(main):
        problems.append("main.tex: \\section belongs in its own sections/*.tex file (one section per file)")

    inputs = INPUT.findall(main)
    if any(not i.startswith("sections/") for i in inputs):
        problems.append(f"main.tex: only sections/*.tex may be input, got {inputs}")
    if len(inputs) != len(set(inputs)):
        problems.append("main.tex: a section file is input more than once")
    files = {"main.tex": main}
    for name in inputs:
        f = paper / (name if name.endswith(".tex") else f"{name}.tex")
        if not f.exists():
            problems.append(f"main.tex inputs {name}, which does not exist")
            continue
        files[str(f.relative_to(paper))] = strip_comments(f.read_text(encoding="utf-8"))
    on_disk = {str(p.relative_to(paper)) for p in (paper / "sections").glob("*.tex")}
    for orphan in sorted(on_disk - set(files)):
        problems.append(f"{orphan} is not input by main.tex")

    for rel, tex in files.items():
        if rel == "main.tex":
            continue
        n = len(SECTION.findall(tex))
        want = 0 if rel == "sections/abstract.tex" else 1
        if n != want:
            problems.append(f"{rel}: has {n} \\section commands, expected {want} (one section per file)")

    for rel, tex in files.items():
        for what, pat in FORBIDDEN.items():
            if pat.search(tex):
                problems.append(f"{rel}: {what} is not allowed (CFP: no spacing/margin/font changes)")

    bib = paper / "references.bib"
    keys = set(BIBKEY.findall(bib.read_text(encoding="utf-8"))) if bib.exists() else set()
    for rel, tex in files.items():
        for group in CITE.findall(tex):
            for key in (k.strip() for k in group.split(",")):
                if key and key not in keys:
                    problems.append(f"{rel}: \\cite key {key!r} is not in references.bib")

    if final:
        for rel, tex in files.items():
            body = tex.replace(r"\newcommand{\todo}", "") if rel == "main.tex" else tex
            if TODO.search(body):
                problems.append(f"{rel}: \\todo left in the final paper")
            for url in PLACEHOLDER_URL.findall(tex):
                problems.append(f"{rel}: placeholder link {url} left in the final paper")
    return problems


def main() -> int:
    args = sys.argv[1:]
    if args not in ([], ["--final"]):
        print(__doc__)
        return 2
    problems = check(final=args == ["--final"])
    for p in problems:
        print(f"paper: {p}", file=sys.stderr)
    if problems:
        return 1
    print("paper lint: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
