"""Tests for the paper lint: the committed paper obeys the CFP format rules and the
one-section-per-file convention, and the lint catches the violations it claims to.

Scope of v0: scripts/check_paper.py on the real paper/ and on synthetic papers.
Out of scope: the LaTeX build and page count (scripts/build_paper.sh needs TeX).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOOD_MAIN = r"""\documentclass[10pt,conference]{IEEEtran}
\newcommand{\todo}[1]{#1}
\begin{document}
\input{sections/abstract}
\input{sections/intro}
\bibliography{references}
\end{document}
"""


def _lint():
    spec = importlib.util.spec_from_file_location("check_paper", ROOT / "scripts" / "check_paper.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_paper"] = mod
    spec.loader.exec_module(mod)
    return mod


def _paper(tmp_path: Path, main: str = GOOD_MAIN, intro: str = "\\section{Intro}\nText~\\cite{a}.\n") -> Path:
    (tmp_path / "sections").mkdir()
    (tmp_path / "main.tex").write_text(main, encoding="utf-8")
    (tmp_path / "sections" / "abstract.tex").write_text(
        "\\begin{abstract}x\\end{abstract}\n", encoding="utf-8"
    )
    (tmp_path / "sections" / "intro.tex").write_text(intro, encoding="utf-8")
    (tmp_path / "references.bib").write_text("@misc{a,\n title={A}}\n", encoding="utf-8")
    return tmp_path


def test_committed_paper_passes_the_lint():
    assert _lint().check() == []


def test_good_synthetic_paper_passes(tmp_path):
    assert _lint().check(_paper(tmp_path), final=True) == []


def test_wrong_documentclass_and_compsoc(tmp_path):
    main = GOOD_MAIN.replace("[10pt,conference]", "[conference,compsoc]")
    problems = _lint().check(_paper(tmp_path, main=main))
    assert any("expected exactly" in p for p in problems)
    assert any("compsoc" in p for p in problems)


def test_spacing_hacks_are_caught_but_comments_are_not(tmp_path):
    intro = "\\section{Intro}\n\\vspace{-2mm}\n% \\linespread{0.9} in a comment is fine\n"
    problems = _lint().check(_paper(tmp_path, intro=intro))
    assert any("negative \\vspace" in p for p in problems)
    assert not any("linespread" in p for p in problems)


def test_one_section_per_file(tmp_path):
    two = "\\section{Intro}\n\\section{Design}\n"
    assert any("2 \\section" in p for p in _lint().check(_paper(tmp_path, intro=two)))


def test_section_in_main_and_orphan_file(tmp_path):
    main = GOOD_MAIN.replace("\\input{sections/intro}", "\\section{Inline}")
    paper = _paper(tmp_path, main=main)
    problems = _lint().check(paper)
    assert any("main.tex: \\section" in p for p in problems)
    assert any("sections/intro.tex is not input" in p for p in problems)


def test_unknown_cite_key(tmp_path):
    intro = "\\section{Intro}\nSee~\\cite{a, missing}.\n"
    assert any("'missing'" in p for p in _lint().check(_paper(tmp_path, intro=intro)))


def test_final_mode_rejects_todos(tmp_path):
    intro = "\\section{Intro}\n\\todo{write me}\n"
    paper = _paper(tmp_path, intro=intro)
    assert _lint().check(paper) == []
    assert any("\\todo left" in p for p in _lint().check(paper, final=True))


def test_final_mode_rejects_placeholder_links(tmp_path):
    intro = "\\section{Intro}\nSee \\url{https://youtu.be/TODO}.\n"
    paper = _paper(tmp_path, intro=intro)
    assert _lint().check(paper) == []
    assert any("placeholder link" in p for p in _lint().check(paper, final=True))
