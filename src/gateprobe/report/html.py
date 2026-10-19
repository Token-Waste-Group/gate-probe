"""Render runs as one self-contained HTML report (no network requests when opened).

Sections: provenance; the floor per gate; the flip table (relation x gate:
flip rate above the floor with its 95% interval, the raw rate, n and repeats,
and the label); transforms (exploratory, collapsed); the reliability diagram
(inline SVG, Jev and the judges on the labeled subset); the threshold band;
the top-20 flip examples with the parent and the variant side by side; the
majority deny -> allow list; cost. Every number shows its repeat count
(`R=`). All text is HTML-escaped, and anything shaped like an API key is
redacted before rendering.

Scope of v0: rendering from rows + variants + the § 3 scores. Out of scope:
the hosted page and the replay bundle (I5).
"""

from __future__ import annotations

import html
import json
import math
import re
from collections import defaultdict
from typing import Any

from gateprobe.analysis.score import CLASSES, index, score
from gateprobe.corpus.schema import Variant

KEY_LIKE = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|hf_[A-Za-z0-9]{10,}|gh[pousr]_[A-Za-z0-9]{10,}|Bearer\s+\S+)")
CLASS_NAMES = {
    "E": "Equivalence",
    "M": "Monotonicity",
    "I": "Irrelevance",
    "A": "Adversarial",
    "P": "Paraphrase",
}
CSS = """
body{font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;color:#1d1f24;background:#fafaf8}
main{max-width:1100px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}
.muted{color:#666}table{border-collapse:collapse;width:100%;margin:8px 0;background:#fff}
th,td{border:1px solid #e3e3e0;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f1f1ee;font-weight:600}td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.positive{background:#fde8e6}.negative{background:#e7f4ea}.neutral{background:#fff}.no_data{color:#999}
code,pre{font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}pre{white-space:pre-wrap;margin:0}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.pair>div{background:#fff;border:1px solid #e3e3e0;padding:8px}
details{margin:8px 0}svg{background:#fff;border:1px solid #e3e3e0}
"""


def redact(text: str) -> str:
    return KEY_LIKE.sub("[redacted]", text)


def esc(value: Any) -> str:
    return html.escape(redact(str(value)))


def num(v: Any, digits: int = 3) -> str:
    return "–" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{digits}f}"


def _repeats(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        out[r["gate_id"]] = max(out[r["gate_id"]], int(r.get("repeat", 0)))
    return out


def _provenance(rows: list[dict[str, Any]]) -> str:
    keys = ("run_id", "gate_id", "model_id", "mode", "git_hash", "config_hash")
    seen = sorted({tuple(r.get(k, "") for k in keys) for r in rows})
    body = "".join("<tr>" + "".join(f"<td><code>{esc(v)}</code></td>" for v in s) + "</tr>" for s in seen)
    return f"<table><tr>{''.join(f'<th>{k}</th>' for k in keys)}</tr>{body}</table>"


def _floor(scored: dict[str, Any], reps: dict[str, int]) -> str:
    out = [
        "<table><tr><th>Gate</th><th>Verdict floor f (95% CI)</th><th>Items</th><th>Probability floor δ</th>"
        "<th>Excluded</th></tr>"
    ]
    for f in scored.get("floor", []):
        flag = " ⚠ over 5%" if f.get("excluded_flag") else ""
        out.append(
            f"<tr><td>{esc(f['gate_id'])}</td><td class=num>{num(f['f'])} [{num(f['f_lo'])}, {num(f['f_hi'])}]"
            f"</td><td class=num>{f['n_items']} (repeat 1 vs 2, R={reps[f['gate_id']]})</td>"
            f"<td class=num>{num(f['delta'])}</td><td class=num>{f['excluded']}{flag}</td></tr>"
        )
    return "".join(out) + "</table>"


def _cell(r: dict[str, Any], reps: int) -> str:
    if not r or not r.get("n_pairs"):
        return "<td class='num no_data'>no data</td>"
    kind = "inversions" if r["rate_kind"] == "risk_inversion" else "flips"
    bonf = " ✱" if r.get("positive_bonferroni") else ""
    return (
        f"<td class='num {esc(r['label'])}'><b>{num(r['excess'], 3)}</b> [{num(r['excess_lo'])}, "
        f"{num(r['excess_hi'])}]<br><span class=muted>{kind} {num(r['rate'])} · n={r['n_pairs']} · R={reps}"
        f"</span><br>{esc(r['label'])}{bonf}</td>"
    )


def _flip_table(scored: dict[str, Any], reps: dict[str, int], key: str = "relations") -> str:
    gates = sorted({r["gate_id"] for r in scored.get(key, [])})
    by = {(r["gate_id"], r["class"], r["transform"]): r for r in scored.get(key, [])}
    rows = sorted(
        {(r["class"], r["transform"]) for r in scored.get(key, [])},
        key=lambda ct: (CLASSES.index(ct[0]), ct[1]),
    )
    out = ["<table><tr><th>Relation</th>" + "".join(f"<th>{esc(g)}</th>" for g in gates) + "</tr>"]
    for cls, transform in rows:
        name = f"{cls} {CLASS_NAMES[cls]}" if transform == "*" else f"{cls} · <code>{esc(transform)}</code>"
        out.append(
            f"<tr><td>{name}</td>"
            + "".join(_cell(by.get((g, cls, transform), {}), reps[g]) for g in gates)
            + "</tr>"
        )
    return "".join(out) + "</table>"


def _reliability_svg(cal: dict[str, Any]) -> str:
    size, pad = 220, 24
    span = size - 2 * pad
    pts = "".join(
        f"<circle cx='{pad + b['confidence'] * span:.1f}' cy='{size - pad - b['accuracy'] * span:.1f}' "
        f"r='{3 + min(6, b['n'] / 3):.1f}' fill='#c0392b' fill-opacity='0.7'><title>bin {b['bin']}: n={b['n']}, "
        f"confidence {b['confidence']:.2f}, accuracy {b['accuracy']:.2f}</title></circle>"
        for b in cal.get("reliability", [])
    )
    return (
        f"<svg width='{size}' height='{size}' role='img' aria-label='reliability diagram'>"
        f"<line x1='{pad}' y1='{size - pad}' x2='{size - pad}' y2='{pad}' stroke='#999' stroke-dasharray='4'/>"
        f"<line x1='{pad}' y1='{size - pad}' x2='{size - pad}' y2='{size - pad}' stroke='#333'/>"
        f"<line x1='{pad}' y1='{size - pad}' x2='{pad}' y2='{pad}' stroke='#333'/>{pts}"
        f"<text x='{size / 2}' y='{size - 4}' font-size='10' text-anchor='middle'>stated / logprob p_block</text>"
        f"<text x='10' y='{size / 2}' font-size='10' transform='rotate(-90 10 {size / 2})' text-anchor='middle'>"
        f"share labeled deny</text></svg>"
    )


def _reliability(scored: dict[str, Any]) -> str:
    cals = [c for c in scored.get("calibration", []) if c.get("n_labeled")]
    if not cals:
        return (
            "<p class=muted>No hand labels yet (C7/H2); the reliability diagram appears once they exist.</p>"
        )
    return (
        "<div style='display:flex;gap:16px;flex-wrap:wrap'>"
        + "".join(
            f"<figure>{_reliability_svg(c)}<figcaption>{esc(c['gate_id'])}: ECE {num(c['ece'])} "
            f"[{num(c['ece_lo'])}, {num(c['ece_hi'])}], n={c['n_labeled']} probes</figcaption></figure>"
            for c in cals
        )
        + "</div>"
    )


def _band(scored: dict[str, Any]) -> str:
    out = [
        "<table><tr><th>Gate</th><th>Widest threshold band no E/I pair crosses</th><th>E/I pairs</th></tr>"
    ]
    for b in scored.get("threshold_band", []):
        if not b.get("defined"):
            text = "not defined (deterministic rule gate)"
        elif b["safe_threshold_exists"]:
            text = f"({num(b['band_lo'])}, {num(b['band_hi'])}] — width {num(b['band_width'])}"
        else:
            text = "no safe threshold"
        out.append(
            f"<tr><td>{esc(b['gate_id'])}</td><td>{text}</td><td class=num>{b.get('n_pairs', '–')}</td></tr>"
        )
    return "".join(out) + "</table>"


def _describe(v: Variant | None) -> str:
    if v is None:
        return "<i>missing</i>"
    call = v.call.get("command") if "command" in v.call else json.dumps(v.call, ensure_ascii=False)
    bits = [
        f"<b>{esc(v.tool)}</b>: <pre>{esc(call)}</pre>",
        f"<span class=muted>policy {esc(v.policy_id)} as {esc(v.policy_rendering)}"
        f"{' (rewritten)' if v.policy_text else ''}; options {esc(v.option_names)}</span>",
    ]
    if v.context:
        bits.append(f"<span class=muted>context:</span><pre>{esc(v.context)}</pre>")
    return "<br>".join(bits)


def _examples(rows: list[dict[str, Any]], variants: dict[str, Variant], limit: int = 20) -> str:
    gates = index(rows)
    cands = []
    for g in gates.values():
        for cls in CLASSES:
            for x, y in g.pairs(cls):
                if 1 not in x.reps or 1 not in y.reps:
                    continue
                (vx, px), (vy, py) = x.reps[1], y.reps[1]
                bad = (vx != vy) if cls != "M" else (vy == "allow" and vx == "deny") or py < px
                if bad:
                    cands.append((abs(py - px), g.gate_id, cls, x, y))
    cands.sort(key=lambda c: (-c[0], c[1], c[4].id))
    if not cands:
        return "<p class=muted>No flips or inversions at repeat 1.</p>"
    out = []
    for dp, gate, cls, x, y in cands[:limit]:
        reps = lambda it: ", ".join(f"{v} {p:.2f}" for _, (v, p) in sorted(it.reps.items()))  # noqa: E731
        out.append(
            f"<h3>{esc(gate)} · {cls} · <code>{esc(y.transform)}</code> · |Δp| {dp:.2f}</h3>"
            f"<div class=pair><div><b>parent</b> — {esc(reps(x))}<br>{_describe(variants.get(x.id))}</div>"
            f"<div><b>variant</b> — {esc(reps(y))}<br>{_describe(variants.get(y.id))}</div></div>"
        )
    return "".join(out)


def _majority(scored: dict[str, Any]) -> str:
    rows = scored.get("majority_inversions", [])
    if not rows:
        return "<p class=muted>None: no M pair's majority verdict goes deny → allow.</p>"
    return (
        "<table><tr><th>Gate</th><th>Variant</th><th>Transform</th><th>p̄ parent → variant</th></tr>"
        + "".join(
            f"<tr><td>{esc(r['gate_id'])}</td><td><code>{esc(r['variant_id'])}</code></td><td>{esc(r['transform'])}</td>"
            f"<td class=num>{num(r['parent_p_mean'])} → {num(r['variant_p_mean'])}</td></tr>"
            for r in rows
        )
        + "</table>"
    )


def _cost(scored: dict[str, Any]) -> str:
    return (
        "<table><tr><th>Gate</th><th>Fresh calls</th><th>USD</th><th>USD / 1,000 calls</th><th>s / 1,000 calls"
        "</th></tr>"
        + "".join(
            f"<tr><td>{esc(c['gate_id'])}</td><td class=num>{c['fresh_calls']}</td><td class=num>{num(c['usd'], 4)}</td>"
            f"<td class=num>{num(c['usd_per_1000_calls'], 4)}</td><td class=num>{num(c['seconds_per_1000_calls'], 1)}"
            "</td></tr>"
            for c in scored.get("cost", [])
        )
        + "</table>"
    )


def render(
    rows: list[dict[str, Any]],
    variants: list[Variant],
    labels: dict[str, str] | None = None,
    title: str = "GateProbe report",
) -> str:
    scored = score(rows, labels)
    reps = _repeats(rows)
    by_id = {v.id: v for v in variants}
    body = [
        f"<h1>{esc(title)}</h1><p class=muted>Scoring rules: docs/RELATIONS.md § 3 (pre-registered). Cells: flip "
        "rate above the test–retest floor with Newcombe 95% interval; red = positive (violation), green = negative "
        f"(invariant within 5 points); ✱ = survives Bonferroni over {scored['bonferroni_tests']} class tests.</p>",
        "<h2>Provenance</h2>",
        _provenance(rows),
        "<h2>Test–retest floor</h2>",
        _floor(scored, reps),
        "<h2>Flip rates above the floor, per relation and gate</h2>",
        _flip_table(scored, reps),
        "<details><summary>Per transform (exploratory)</summary>",
        _flip_table(scored, reps, "transforms"),
        "</details>",
        "<h2>Reliability on the hand-labeled subset</h2>",
        _reliability(scored),
        "<h2>Threshold band</h2>",
        _band(scored),
        "<h2>Top 20 flips and inversions (repeat 1)</h2>",
        _examples(rows, by_id),
        "<h2>Majority deny → allow under a riskier call</h2>",
        _majority(scored),
        "<h2>Cost</h2>",
        _cost(scored),
    ]
    return (
        f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport "
        f"content='width=device-width,initial-scale=1'><title>{esc(title)}</title><style>{CSS}</style></head>"
        f"<body><main>{''.join(body)}</main></body></html>\n"
    )
