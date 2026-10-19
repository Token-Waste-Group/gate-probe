#!/usr/bin/env python3
"""Generate the P class (C8) with the configured open model, or rebuild it from the frozen outputs.

The model, prompts and decoding are in configs/paraphrase.yaml.

    uv run python scripts/paraphrase.py --base-url http://localhost:8001   # ask the model (vLLM)
    uv run python scripts/paraphrase.py --rebuild    # no model: from variants/paraphrase_raw.json

Writes variants/paraphrase_raw.json (every model output, rejected ones with the
reason), variants/paraphrase.jsonl (the P variants, kept apart from
generated.jsonl) and variants/paraphrase.sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from gateprobe.corpus.schema import Probe, Variant, load_jsonl
from gateprobe.relations.expand import to_jsonl
from gateprobe.relations.paraphrase import build, generate, load_config, openai_complete

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "variants" / "paraphrase_raw.json"
OUT = ROOT / "variants" / "paraphrase.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--base-url", help="OpenAI-compatible endpoint serving the configured model")
    group.add_argument("--rebuild", action="store_true", help="rebuild the variants from the frozen outputs")
    args = parser.parse_args()
    if args.base_url:
        cfg = load_config(ROOT / "configs" / "paraphrase.yaml")
        probes = load_jsonl(ROOT / "probes" / "corpus.jsonl", Probe)
        raw = generate(probes, ROOT / "policies", cfg, openai_complete(args.base_url, cfg))
        RAW.write_text(json.dumps(raw, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    variants = build(raw, load_jsonl(ROOT / "variants" / "generated.jsonl", Variant))
    text = to_jsonl(variants)
    OUT.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (ROOT / "variants" / "paraphrase.sha256").write_text(f"{digest}  paraphrase.jsonl\n", encoding="utf-8")
    statuses = Counter(r["status"] for r in raw["commands"])
    n_pol = len(raw["policies"])
    print(f"commands {dict(statuses)}; policies {n_pol}; {len(variants)} P variants -> {OUT.name}")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
