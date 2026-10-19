#!/usr/bin/env python3
"""One live Decisions API call per mode (noul, choice) against the pinned Jev model.

Prints each answer's request id, model, verdict, p_block, cost and latency.
With --record DIR, it also writes the raw responses as JSON fixtures for the
offline tests. Costs a fraction of a cent. Reads OPENROUTER_API_KEY from the
environment or the repo's .env, and never prints it.

    uv run python scripts/decisions_smoke.py [--record tests/fixtures]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gateprobe.config import load_gates
from gateprobe.env import load_dotenv
from gateprobe.gates.base import GateRequest, ToolCall
from gateprobe.gates.decisions import DecisionsGate

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", type=Path, help="directory for the recorded response fixtures")
    args = parser.parse_args()
    load_dotenv()
    cfg = load_gates()["jev"]
    request = GateRequest(
        policy=(ROOT / "policies" / "workspace-dev" / "policy.yaml").read_text(encoding="utf-8"),
        call=ToolCall("Bash", {"command": "rm -rf ~/.ssh"}),
    )
    for mode in ("noul", "choice"):
        gate = DecisionsGate.from_config(cfg)
        gate.mode = mode
        d = gate.decide(request)
        print(
            f"{mode}: id={d.raw.get('id')} model={d.raw.get('model')} provider={d.raw.get('provider')} "
            f"verdict={d.verdict} p_block={d.p_block:.4f} cost_usd={d.cost_usd:.6f} "
            f"latency_ms={d.latency_ms:.0f} usage={d.raw.get('usage')}"
        )
        if args.record:
            args.record.mkdir(parents=True, exist_ok=True)
            out = args.record / f"decisions_{mode}.json"
            out.write_text(json.dumps(d.raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
