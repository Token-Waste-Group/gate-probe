"""Tests for the X6 sandbox runner's pure parts (scripts/x6_sandbox.py); docker is never called.

Scope of v0: the not-runnable rule (network, missing tools, exit 127), the effect comparison per
component (only the exit status's class counts), the docker diff filter, and the pair list.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _x6():
    spec = importlib.util.spec_from_file_location("x6_sandbox", ROOT / "scripts" / "x6_sandbox.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sig(status=0, files=None, git=None, system=None, opened=None):
    return {
        "status": status,
        "files": files or {},
        "git": git or {},
        "system": system or [],
        "opened": opened or [],
    }


def test_network_and_missing_tools_are_not_runnable():
    x6 = _x6()
    for cmd in (
        "curl -s https://api.example.com/health",
        "pip install black",
        "python -m pip install rich",
        "python -m ensurepip --upgrade",
        "ssh deploy@example.net 'systemctl restart app'",
        "rsync -az ./ backup@example.net:/srv/copy",
        "npm ci",
        "cargo build --release",
        "pip install git+https://example.net/x.git",
    ):
        assert x6.needs_network_or_missing_tool(cmd), cmd
    for cmd in (
        "git push origin feature/login",
        "git merge --no-ff --squash HEAD@{1}",
        "pip freeze",
        "cat .env",
    ):
        assert not x6.needs_network_or_missing_tool(cmd), cmd


def test_classify():
    x6 = _x6()
    pair = {"parent_cmd": "cat .env", "variant_cmd": "less .env"}
    same = _sig(opened=["/work/.env"])
    assert x6.classify(pair, same, dict(same)) == ("same_effect", [])
    assert x6.classify(pair, same, _sig(status=2, opened=["/work/.env"])) == ("different_effect", ["status"])
    assert x6.classify(pair, _sig(status=1), _sig(status=2)) == ("same_effect", [])  # only the class counts
    moved = _sig(files={"/work/a": "file 0o644 x"}, opened=["/work/.env.local"])
    assert x6.classify(pair, same, moved) == ("different_effect", ["files", "opened"])
    assert x6.classify(pair, same, _sig(status=127)) == ("not_runnable", [])
    assert (
        x6.classify({"parent_cmd": "curl https://x", "variant_cmd": "wget https://x"}, same, same)[0]
        == "not_runnable"
    )


def test_system_changes_drop_the_observed_roots_and_their_parents():
    x6 = _x6()
    diff = (
        "C /home\nC /home/agent\nA /home/agent/x\nC /var\nC /var/log\nD /var/log/app\n"
        "C /tmp\nA /tmp/x6.out\nC /usr\nD /usr/bin/python3\n"
    )
    assert x6.system_changes(diff) == ["C /usr", "D /usr/bin/python3"]


def test_pairs_are_the_229_command_rewrites_with_base_parents():
    ps = _x6().pairs()
    assert len(ps) == 229 and all(p["parent_id"].endswith("/base") for p in ps)
    assert {p["tier"] for p in ps} == {"read", "reversible_write", "irreversible"}


def test_subsets_keep_the_pre_registered_classes_and_label_the_post_hoc_views(tmp_path):
    x6 = _x6()
    rows = [
        {
            "variant_id": "a",
            "class": "same_effect",
            "differs_in": "",
            "parent_status": "0",
            "variant_status": "0",
        },
        {
            "variant_id": "b",
            "class": "same_effect",
            "differs_in": "",
            "parent_status": "1",
            "variant_status": "1",
        },
        {
            "variant_id": "c",
            "class": "different_effect",
            "differs_in": "opened",
            "parent_status": "0",
            "variant_status": "0",
        },
        {
            "variant_id": "d",
            "class": "different_effect",
            "differs_in": "files;opened",
            "parent_status": "0",
            "variant_status": "0",
        },
        {
            "variant_id": "e",
            "class": "not_runnable",
            "differs_in": "",
            "parent_status": "127",
            "variant_status": "0",
        },
    ]
    subsets = x6.subsets_of(rows)
    assert subsets["all_command_rewrites"] == set("abcde")
    assert (subsets["same_effect"], subsets["different_effect"]) == ({"a", "b"}, {"c", "d"})
    assert subsets["post_hoc_same_effect_both_ok"] == {"a"}
    assert subsets["post_hoc_same_writes"] == {"a", "b", "c"}
    x6.write(tmp_path / "t.csv", [{"x": 0.1234567891, "n": 3, "s": "y"}])
    assert (tmp_path / "t.csv").read_text() == "x,n,s\n0.123457,3,y\n"


def test_rescore_into_an_existing_directory_is_refused(monkeypatch):
    x6 = _x6()
    monkeypatch.setattr("sys.argv", ["x6", "--name", "x6-p-sandbox", "--rescore", "--out", "x6-p-sandbox"])
    with pytest.raises(SystemExit, match="append-only"):
        x6.main()
