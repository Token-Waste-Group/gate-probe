# Policies

Four authorization policies for a coding agent, each rendered four ways:

| File | Rendering | Role |
|---|---|---|
| `policy.yaml` | YAML | the parent's canonical rendering (`docs/RELATIONS.md` § 1) |
| `policy.json` | JSON | `policy_format` variant |
| `policy.prose.md` | one prose paragraph | `policy_format` variant |
| `policy.bullets.md` | bullet list | `policy_format` variant |

Policies: `workspace-dev` (develops locally, pushes nothing), `read-only-review`
(changes nothing), `ci-maintainer` (keeps the build green, publishes nothing),
`release-manager` (pushes to origin and publishes, rewrites no history).

**One source.** Every rendering is generated from `configs/policies.yaml` by
`uv run python scripts/render_policies.py`. Never edit a rendering by hand.
A rule is (effect, action, scope); every rendering states the same semantics
(anything not allowed is denied; deny overrides allow). The YAML and JSON
renderings carry a glossary of the actions and scopes they use, so all four are
self-contained. `tests/test_policies.py` checks that the committed files match a
fresh render, that YAML and JSON parse back to the source rules, and that prose
and bullets state every rule.

**Provenance.** All four renderings are generated from the policy sources by
`gateprobe/corpus/render.py`; none is reused from elsewhere.

**Rule sets.** `policies/<id>/rules.yaml` holds the rule gate's allow and deny
lists in Claude Code permission syntax (R3). They are **hand-written** to match
each policy: not generated from it, and not guaranteed equivalent to it. They
are what an administrator would plausibly configure. The rule gate reads the
policy id, never a rendering, so the `policy_format` transform can't flip it by
construction. Command-text patterns can still flip on flag, whitespace or path
spellings, and those are exactly the coverage gaps the baseline is meant to
show. Semantics: `gateprobe/gates/rules.py`.
