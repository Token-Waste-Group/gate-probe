"""The P class: an open model rewrites a probe's command or its policy, and the rewrite becomes a variant.

Two transforms (docs/RELATIONS.md § 2): `command_paraphrase` (the Bash command
rewritten with the same effect, e.g. `rm -rf build` -> `find build -delete`)
and `policy_paraphrase` (the policy's prose rendering reworded). The model, its
revision, the prompts and the temperature are fixed in `configs/paraphrase.yaml`.

Generation and building are separate. `generate` asks the model and returns the
raw outputs (kept in `variants/paraphrase_raw.json`, with every rejected output
and the reason). `build` turns those outputs into variants with no model, so the
frozen set is reproducible byte for byte. A command rewrite is rejected when it
is not one non-empty line, or when it is the same call as the original after
normalization (that would be an E variant, not a paraphrase).

A `command_paraphrase` variant's parent is the base item. A `policy_paraphrase`
variant's parent is the probe's `policy_format` variant in the prose rendering,
so the pair isolates the rewording from the YAML -> prose change (which E already
measures).

Scope of v0: one rewrite per command and one per policy; an OpenAI-compatible
chat endpoint (vLLM). Out of scope: checking that a rewrite really is
equivalent; the hand-checked sample (docs/PARAPHRASE.md) and X6 (sandbox) do that.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from gateprobe.corpus.render import FILES
from gateprobe.corpus.schema import Probe, Variant
from gateprobe.relations.normalize import normalize

# prompt -> (answer text, served model id)
Complete = Callable[[str], tuple[str, str]]


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def openai_complete(base_url: str, cfg: dict[str, Any], timeout_s: float = 300.0) -> Complete:
    """A `Complete` over an OpenAI-compatible chat endpoint, with the config's model, temperature and seed."""
    from gateprobe.gates.transport import urllib_transport

    post = urllib_transport(timeout_s)

    def complete(prompt: str) -> tuple[str, str]:
        body = {
            "model": cfg["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": cfg["temperature"],
            "seed": cfg["seed"],
            "max_tokens": cfg["max_tokens"],
            "chat_template_kwargs": {"enable_thinking": cfg["enable_thinking"]},
        }
        url = base_url.rstrip("/") + "/v1/chat/completions"
        status, out = post(url, {"Content-Type": "application/json"}, body)
        if status != 200:
            raise RuntimeError(f"paraphrase endpoint returned {status}: {str(out)[:200]}")
        return out["choices"][0]["message"]["content"], out.get("model", "")

    return complete


def _fill(template: str, **values: str) -> str:
    for k, v in values.items():
        template = template.replace("{" + k + "}", v)
    return template


def parse_command(text: str, original: str) -> tuple[str | None, str]:
    """(the rewritten command or None, status): ok, no_json, not_one_line, same_call."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        cmd = json.loads(m.group(0))["command"] if m else None
    except (json.JSONDecodeError, KeyError, TypeError):
        cmd = None
    if not isinstance(cmd, str) or not cmd.strip():
        return None, "no_json"
    cmd = cmd.strip()
    if "\n" in cmd:
        return None, "not_one_line"
    if normalize("Bash", {"command": cmd}) == normalize("Bash", {"command": original}):
        return None, "same_call"
    return cmd, "ok"


def generate(
    probes: list[Probe], policies_dir: Path, cfg: dict[str, Any], complete: Complete
) -> dict[str, Any]:
    commands = []
    served = set()
    for p in sorted(probes, key=lambda p: p.id):
        if p.tool != "Bash" or p.risk_tier in cfg["command_skip_tiers"]:
            continue
        original = p.call["command"]
        text, model = complete(_fill(cfg["command_prompt"], command=original))
        served.add(model)
        rewrite, status = parse_command(text, original)
        commands.append(
            {"probe_id": p.id, "original": original, "output": text, "rewrite": rewrite, "status": status}
        )
    policies = []
    for pid in sorted({p.policy_id for p in probes}):
        original = (Path(policies_dir) / pid / FILES["prose"]).read_text(encoding="utf-8").strip()
        text, model = complete(_fill(cfg["policy_prompt"], policy=original))
        served.add(model)
        rewrite = text.strip()
        policies.append(
            {
                "policy_id": pid,
                "original": original,
                "rewrite": rewrite,
                "status": "ok" if rewrite else "empty",
            }
        )
    keys = ("model", "revision", "served_by", "temperature", "seed", "max_tokens", "enable_thinking")
    generator = {k: cfg[k] for k in keys} | {"served_model": sorted(served)}
    return {"generator": generator, "commands": commands, "policies": policies}


def build(raw: dict[str, Any], generated: list[Variant]) -> list[Variant]:
    """The P variants from the raw outputs and the E/M/I/A set (for the parents), with no model."""
    seed = raw["generator"]["seed"]
    by_id = {v.id: v for v in generated}
    prose_parent = {
        v.probe_id: v for v in generated if v.transform == "policy_format" and v.policy_rendering == "prose"
    }
    policy_text = {r["policy_id"]: r["rewrite"] for r in raw["policies"] if r["status"] == "ok"}
    out = []
    for r in raw["commands"]:
        if r["status"] != "ok":
            continue
        base = by_id[f"{r['probe_id']}/base"]
        out.append(
            Variant.from_dict(
                base.to_dict()
                | {
                    "id": f"{r['probe_id']}/command_paraphrase/0",
                    "parent_id": base.id,
                    "relation_class": "P",
                    "transform": "command_paraphrase",
                    "expected": "unchanged",
                    "call": {"command": r["rewrite"]},
                    "seed": seed,
                }
            )
        )
    for probe_id, parent in sorted(prose_parent.items()):
        if parent.policy_id not in policy_text:
            continue
        out.append(
            Variant.from_dict(
                parent.to_dict()
                | {
                    "id": f"{probe_id}/policy_paraphrase/0",
                    "parent_id": parent.id,
                    "relation_class": "P",
                    "transform": "policy_paraphrase",
                    "expected": "unchanged",
                    "policy_text": policy_text[parent.policy_id],
                    "seed": seed,
                }
            )
        )
    return sorted(out, key=lambda v: v.id)
