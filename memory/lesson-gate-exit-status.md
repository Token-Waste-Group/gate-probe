# Lesson: never let a pipe or an unprotected branch hide a red gate

**Type:** lesson (carried over from the authority repo, 2026-10-08).
**Audience:** every agent merging PRs here.

In the authority repo a PR merged with a failing gate. Two things combined:

- `bash scripts/check.sh | tail -1 && …` takes **`tail`'s** exit status, not
  the gate's, so the chain carried on after `Found 3 errors.`
- `main` had **no branch protection**, so `gh pr merge` merged a PR whose CI
  failed, and `gh pr checks --watch` only waits; it doesn't block.

**How to apply:**
- Run the gate as `bash scripts/check.sh > log 2>&1; [ $? -eq 0 ]`, or with
  `set -o pipefail`. Never put `| tail` before an `&&`.
- Merge only after reading the CI conclusion:
  `gh pr view N --json statusCheckRollup -q '.statusCheckRollup[0].conclusion'`
  must be `SUCCESS`.
- Mark a step done only after `gh pr view N --json state` returns `MERGED`.
- **Read the job, not the run.** In gate-probe on 2026-10-19, `gh run list`
  showed PR #1's run as `completed / success` while its only job, `gate`, was
  still `queued` with no steps. Check
  `gh run view <id> --json jobs -q '.jobs[] | {name, status, conclusion}'`:
  the `gate` job itself must be `completed / success`.
- **No branch protection here** (human decision, 2026-10-19): nothing on
  GitHub stops a red merge, so the checks above are the only safeguard. Never
  skip them.

See [[decision-autonomy-loop]].
