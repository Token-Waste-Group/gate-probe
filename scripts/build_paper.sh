#!/usr/bin/env bash
# Build paper/main.pdf and enforce the CFP's hard rules (docs/icse27-demo-cfp.md):
# the format lint (scripts/check_paper.py), then at most 4 pages INCLUDING
# references. `--final` also fails on any \todo left. Needs latexmk + pdfinfo.
#   bash scripts/build_paper.sh [--final]
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
max_pages=4

python3 "$root/scripts/check_paper.py" "$@"

cd "$root/paper"
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error main.tex > build.log 2>&1 || {
  echo "paper: LaTeX build failed — see paper/build.log" >&2
  grep -E '^[^:]+:[0-9]+:|^! ' build.log | head -20 >&2 || true
  exit 1
}

pages="$(pdfinfo main.pdf | awk '/^Pages:/ {print $2}')"
if grep -qE 'Citation .* undefined|Reference .* undefined' main.log; then
  echo "paper: WARN undefined citations or references — see paper/main.log" >&2
fi
if [ "$pages" -gt "$max_pages" ]; then
  echo "paper: $pages pages — the CFP allows $max_pages including references" >&2
  exit 1
fi
echo "paper: OK ($pages/$max_pages pages) -> paper/main.pdf"
