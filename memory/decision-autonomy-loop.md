# Decision: the autonomous /continue loop

**Type:** decision. **Audience:** every Claude in this repo.

The project advances via a single mechanism: **`docs/PLAN.md` (the living plan +
claim ledger) driven by the `/continue` runbook** (`.claude/commands/continue.md`)
and the helpers in `scripts/`. Full spec: `docs/AUTONOMY.md`. Adapted on
2026-10-19 from the latent-underspecification-research loop.

**Key rules to remember:**
- Saying «продолжи» / `/continue [lane]` = claim the next eligible step (in that
  lane), implement its `done-when`, gate (`scripts/check.sh`), open a PR,
  **auto-merge only when green and CI says SUCCESS**, then `mark.py <id> done`.
  **Exactly one step per invocation**, with human checkpoints: **announce the
  plan before starting**, and at the end **report + ask before continuing**
  (never auto-advance).
- **Lanes = workstreams:** S shared, C corpus/relations (P1), R + X
  runner/analysis/runs (P2), I integrations/packaging (P3), W paper/video (P4),
  G decision points, H human tasks. Each owner's agent runs `/continue <lane>`.
- **Never hand-edit step statuses** while working — `scripts/claim.py` /
  `scripts/mark.py` do it atomically (git push is the lock; losers re-pick).
  This is what makes parallel agents safe.
- **Hardware-aware claiming:** `[API: OpenRouter]` needs the key with credit,
  `[API: Anthropic]` needs `ANTHROPIC_API_KEY`;
  `[GPU: H100]` needs the VPN and the `d.dgx` alias (the H100 is driven over
  ssh from a laptop). Peek with `claim.py --dry-run`, skip what you can't run
  with `--skip-tag API|GPU`, release a mis-claim with `mark.py <id> todo
  "<reason>"`. A stuck claim on a five-day sprint is schedule damage.
- **`[HUMAN]` steps are never claimed** — `--dry-run` lists them; report them.
  **`[GATE]` steps** end with the packet merged and the step `blocked "awaiting
  human decision"`; the humans mark them done.
- **Plan changes need a human.** Adding/splitting/re-sequencing steps must be
  *proposed and confirmed* before editing `docs/PLAN.md`'s step set; the loop
  only updates statuses automatically. `cut` is human-only.
- **Blocked > forced.** Unresolvable conflict / failing upstream / ambiguous
  spec / a fallback trigger → `mark.py <id> blocked "<reason>"` and stop for a
  human. Never force a merge. G1–G3 and the fallbacks are **always** human
  decisions — see [[decision-research-discipline]].

**How to apply:** when the user wants progress, run `/continue`. When you finish
a step, leave `docs/PLAN.md` and `STATUS.md` accurate so the next agent (or
you) resumes cleanly. Merging: [[lesson-gate-exit-status]],
[[lesson-preregistration-git-trail]].
