# Lesson: keep the rule-before-result trail visible in git

**Type:** lesson (carried over from the latent-underspecification project,
where reviewers asked "where is the pre-registration?"). **Audience:** every
Claude running an X step.

The answer to that question is the git trail: the report with its decision rule
is committed (status `planned`) **before** the run, and every result row
carries the code's git hash. The trail is fragile in three ways:

- **Squash-merging erases it.** A squash leaves only the combined commit on
  `main`; the rule-before-result commit survives only in GitHub PR history.
  **Merge X-step PRs with `gh pr merge --merge`** (not `--squash`).
- **Rebasing resets committer dates.** Author dates and file contents survive.
  If you rebase, cite author dates and record the pre→post-rebase SHA mapping
  in the report.
- **Only call it pre-registered if a timestamped commit exists.** Here the
  scoring rules live in `docs/RELATIONS.md` (merged at C1, frozen at G1) and
  each X report copies them before its run. Say "pre-registered" in the paper
  only when those commits precede the first result row.

**How to apply:** for X steps, commit and push the planned report first, then
run, then commit results as a separate commit; merge with `--merge`. See
[[decision-research-discipline]].
