#!/usr/bin/env bash
# Idempotent environment bootstrap for the autonomous loop. Cross-platform
# (macOS laptop / Linux boxes). Safe to re-run. See docs/AUTONOMY.md.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

# 1. uv (package/venv manager)
if ! command -v uv >/dev/null 2>&1; then
  echo "installing uv ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# 2. project venv + package (CI uses 3.11; pin the same minor locally)
[ -d .venv ] || uv venv --python 3.11
uv pip install -e ".[dev]"

# 3. working dirs (cache/ and runs/ are git-ignored)
mkdir -p probes policies variants cache runs results paper

# 4. soft prerequisites (warn, don't fail)
if command -v gh >/dev/null 2>&1; then
  gh auth status >/dev/null 2>&1 || echo "WARN: gh not authenticated — run 'gh auth login' for PR/auto-merge"
else
  echo "WARN: gh CLI missing — PR/auto-merge unavailable"
fi
{ [ -f .env ] && grep -q '^OPENROUTER_API_KEY=.' .env; } \
  || echo "WARN: OPENROUTER_API_KEY not set in .env — [API: OpenRouter] steps (Decisions API runs) will fail; code/test steps are fine"
{ [ -f .env ] && grep -q '^ANTHROPIC_API_KEY=.' .env; } \
  || echo "WARN: ANTHROPIC_API_KEY not set in .env — [API: Anthropic] steps (the Claude judge) will fail; code/test steps are fine"
command -v docker >/dev/null 2>&1 || echo "WARN: docker missing — the Docker image steps (I4, I5) can't run here"
command -v latexmk >/dev/null 2>&1 || echo "WARN: latexmk missing — paper builds (W steps) can't run here"
echo "NOTE: [GPU: H100] steps drive d.dgx over ssh (VPN up, alias in ~/.ssh/config) — read memory/reference-dgx-usage.md first"

echo "bootstrap: OK"
