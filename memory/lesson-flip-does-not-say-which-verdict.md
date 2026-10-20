# Lesson: a metamorphic flip proves one verdict wrong, not which one

**Type:** lesson (X5, 2026-10-20). **Audience:** every Claude choosing examples for the paper, the video or a report.

An E, P or M violation means the gate contradicts itself: the two verdicts can't both be right. It does not say which one is wrong. In X5, the rule "largest drop among destructive E flips" picked Luna's `git branch -D feature/old`, deny → allow after a re-rendering. But the ci-maintainer policy literally *allows* local branch changes, so it was the original *deny* that was off. The "auto-approved" framing would have misled.

**How to apply:**
- When a case study or caption claims a gate *approved what it should not*, pre-register a condition on the policy's literal verdict: the policy must deny the call. Name the policy clause.
- Otherwise call it a self-contradiction.
- If you only notice afterwards, keep the rule's pick as the result and label any better example as post hoc (as X5 does).

See [[lesson-read-top-transforms]].
