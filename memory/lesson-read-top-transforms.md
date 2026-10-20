# Lesson: read top_transforms.csv after every analysis, before writing the report

**Type:** lesson (X4, 2026-10-20). **Audience:** every Claude running `gateprobe analyze`.

RELATIONS § 5 asks each X report to list the five most-flipping transforms per gate, with an example each, so that humans can check every table entry is truly equivalent or truly riskier. X1, X3 and X7 skipped it. When X4 added `top_transforms.csv` (`analyze --variants … ` fills in the inputs), it found a generator bug at once: `path_normalization` rewrote the rsync remote `backup@example.net:/srv/copy` as `$PWD/backup@…`, which is a local path. The generator skips `scp`, `ssh` and `curl` operands, but not `rsync`'s. Only the Claude judge flipped on it, and it was right to.

**How to apply:**
- Pass `--variants variants/generated.jsonl variants/paraphrase.jsonl` to `analyze`, and read `top_transforms.csv` before you write the Data section.
- A non-equivalent entry is a generator bug, not a gate failure. Report it with its effect, e.g. the label with and without the pairs (descriptive).
- Never fix or drop pairs silently. After G1 the generators are frozen, so fixing one is a human call.

See [[lesson-flip-does-not-say-which-verdict]].
