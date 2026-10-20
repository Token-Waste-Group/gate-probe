"""Tests for the replay bundle (scripts/build_bundle.py) and the replay check (scripts/compare_runs.py), I5.

Scope of v0: the bundle holds exactly the cache entries behind answered rows (ok, refusal), the
runs and their batch logs, a manifest that verifies, and BUNDLE.json; the archive is
byte-for-byte deterministic; a missing entry stops the build. The check treats a frozen error
and a replayed miss as the same non-answer and reports any other difference.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(variant: str, repeat: int, status: str, key: str | None, p: float | None = None) -> dict:
    row = {"gate_id": "g", "variant_id": variant, "repeat": repeat, "status": status}
    if key:
        row["cache_key"] = key
    if p is not None:
        row |= {"verdict": "deny" if p >= 0.5 else "allow", "p_block": p}
    return row


@pytest.fixture
def root(tmp_path):
    bb = _load("build_bundle")
    for p in bb.INPUTS:
        (tmp_path / p).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / p).write_text(p)
    rows = [
        _row("v/base", 1, "ok", "k1", 0.9),
        _row("v/base", 2, "refusal", "k2"),
        _row("v/base", 3, "error", "k3"),  # never answered: no cache entry
        _row("v/x", 1, "not_applicable", None),
    ]
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "a.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "runs" / "a.batches.json").write_text("{}")
    (tmp_path / "cache").mkdir()
    for k in ("k1", "k2", "unused"):
        (tmp_path / "cache" / f"{k}.json").write_text(json.dumps({"key": k}))
    return tmp_path


def _members(path: Path) -> dict[str, bytes]:
    with tarfile.open(path) as tar:
        return {m.name: tar.extractfile(m).read() for m in tar.getmembers()}


def test_bundle_holds_the_answered_entries_and_a_manifest_that_verifies(root, tmp_path):
    bb = _load("build_bundle")
    path = bb.build(tmp_path / "out", root, runs=("a",), commit="abc")
    files = _members(path)
    name = f"gateprobe-replay-{bb.RESULTS}"
    assert sorted(files) == sorted(
        f"{name}/{p}"
        for p in (
            "BUNDLE.json",
            "MANIFEST.sha256",
            "README.md",
            "cache/k1.json",
            "cache/k2.json",
            "runs/a.batches.json",
            "runs/a.jsonl",
        )
    )
    manifest = files[f"{name}/MANIFEST.sha256"].decode().splitlines()
    assert len(manifest) == 6
    for line in manifest:
        digest, p = line.split("  ")
        assert hashlib.sha256(files[f"{name}/{p}"]).hexdigest() == digest
    meta = json.loads(files[f"{name}/BUNDLE.json"])
    assert (meta["rows"], meta["cache_entries"], meta["built_from"]) == (4, 2, "abc")
    assert meta["inputs_sha256"]["configs/gates.yaml"] == hashlib.sha256(b"configs/gates.yaml").hexdigest()
    assert "--allow-misses" in files[f"{name}/README.md"].decode()
    sidecar = (path.parent / f"{path.name}.sha256").read_text()
    assert sidecar == f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"


def test_bundle_is_deterministic_and_stops_on_a_missing_entry(root, tmp_path):
    bb = _load("build_bundle")
    one = bb.build(tmp_path / "one", root, runs=("a",), commit="abc").read_bytes()
    two = bb.build(tmp_path / "two", root, runs=("a",), commit="abc").read_bytes()
    assert one == two
    with tarfile.open(fileobj=io.BytesIO(one)) as tar:
        assert {(m.mtime, m.uid, m.mode) for m in tar.getmembers()} == {(0, 0, 0o644)}
    (root / "cache" / "k2.json").unlink()
    with pytest.raises(SystemExit, match="1 cache entries"):
        bb.build(tmp_path / "three", root, runs=("a",), commit="abc")


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_compare_runs(tmp_path):
    cr = _load("compare_runs")
    frozen = cr.answers(
        [
            _write(
                tmp_path / "f.jsonl",
                [_row("v", 1, "ok", "k", 0.9), _row("v", 2, "error", "k"), _row("v", 3, "ok", "k", 0.4)],
            )
        ]
    )
    same = cr.answers(
        [_write(tmp_path / "r.jsonl", [_row("v", 1, "ok", "k", 0.9), _row("v", 2, "replay_miss", "k")])]
    )
    assert cr.compare(frozen, same) == (2, [])
    moved = cr.answers([_write(tmp_path / "m.jsonl", [_row("v", 3, "ok", "k", 0.6)])])
    assert cr.compare(frozen, moved) == (1, [("g", "v", 3)])
    assert cr.compare(frozen, {}) == (0, [])
