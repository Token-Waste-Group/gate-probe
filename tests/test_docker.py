"""Tests for the container packaging: no secrets in the build context, and provenance without git.

Scope of v0: .dockerignore, the Dockerfile's provenance build arg, and git_hash's
fallback (the image has no git). Out of scope: building the image (needs a
Docker daemon; checked by hand in I4 and on a clean machine in I5).
"""

from __future__ import annotations

from pathlib import Path

from gateprobe.runner import run

ROOT = Path(__file__).resolve().parents[1]


def test_dockerignore_keeps_secrets_and_local_state_out():
    ignored = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert {".env", ".env.*", ".git", ".venv", ".claude", "memory", "cache", "runs"} <= ignored


def test_dockerfile_bakes_provenance_and_runs_the_cli():
    text = (ROOT / "Dockerfile").read_text()
    assert "ARG GIT_HASH" in text and "GATEPROBE_GIT_HASH=$GIT_HASH" in text
    assert 'ENTRYPOINT ["gateprobe"]' in text and "pip install -e" in text


def test_git_hash_falls_back_without_git(monkeypatch):
    def no_git(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(run.subprocess, "run", no_git)
    monkeypatch.setenv("GATEPROBE_GIT_HASH", "abc123")
    assert run.git_hash() == "abc123"
    monkeypatch.delenv("GATEPROBE_GIT_HASH")
    assert run.git_hash() == "unknown"
