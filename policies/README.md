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

**Provenance.** The plan assumed these renderings could be reused from an
earlier internal codebase (examined at commit `088d0ab`, 16 Oct 2026). They
could not: its renderers serialize a Cedar-style principal/action/resource
model for entity authorization, and none of them produces YAML or bullets.
So no rendering was reused; all four come from `gateprobe/corpus/render.py`.
That codebase is unpublished and is not cited (`CLAUDE.md` invariant 13).

**Rule sets** for the rule gate (`policies/<id>/rules.yaml`, Claude Code-style
permission patterns) are hand-written per policy in step R3.
