# Run reports

Every run (X step) in this project produces a committed report here —
**including negative or failed results**. A "fail" is a finding, not something
to bury: silently dropping a negative result is forbidden (see the Results rule
in `CLAUDE.md` / `docs/AUTONOMY.md`). A relation that shows no flips above the
floor is a result too — the plan says the paper then leads with M and A.

## Rules

- One report per run step: `docs/experiments/<step-id>-<slug>.md` (e.g.
  `x1-jev-rules.md`).
- A step that makes an empirical claim is **not `done` until its report is
  committed** with a result.
- The report must contain:
  1. **Question** — which RQ(s), which gates, which relation classes.
  2. **Method** — corpus and variant set (with their hashes), gates and their
     **pinned model ids**, adapter mode (Noul / Choice), repeats, the $ cap,
     and the **exact reproduce command** (one CLI invocation + one config) plus
     the replay command.
  3. **Decision rule** — copied from `docs/RELATIONS.md` *before* running (what
     counts as a violation, the floor, when a relation is reported as violated
     for a gate). Never edited after the results are in.
  4. **Data** — per gate: the test–retest floor; per relation: flip rate above
     the floor with Wilson 95% interval and n; mean |Δp_block|; for M the
     risk-inversion share by transform; spend and wall-clock. Git hash and
     config hash recorded.
  5. **Result** — classified **positive | neutral | negative** per relation and
     gate.
  6. **Conclusion & implication** — what we now believe; what changes for the
     paper. Anything that trips a fallback trigger is flagged for the humans.
- **Raw artifacts stay out of git** (`cache/`, `runs/` are git-ignored and ship
  as the replay bundle). Commit only the report + distilled numbers (`results/`
  CSVs are append-only).
- **Commit order is the pre-registration:** push the report with `status:
  planned` before launching, commit the results separately, and merge the PR
  with `--merge` (`memory/lesson-preregistration-git-trail.md`).
- After G3 (Thu 22 12:00) no new rows enter `results/`.

## Template

```markdown
# <Title> (<step-id>)
- status: planned | done
- result: — | positive | neutral | negative   (per relation in the Data table)

## Question
## Method (+ reproduce and replay commands)
## Decision rule (pre-registered)
## Data
## Result
## Conclusion & implication
```

## Index

(populated as steps complete)
