# Lesson: under strace, sudo can't elevate, so traced sandboxes can't test sudo commands

**Type:** lesson (X6, 2026-10-20). **Audience:** anyone building a sandbox that traces commands.

X6 ran each command under `strace -f` to record the files it opened. The kernel ignores setuid on a traced process, so `sudo` fails with "effective uid is not 0", even with passwordless sudo. Every `sudo …` pair therefore "both failed, nothing changed" and was classed same effect, though it was never really run. The report states this.

**How to apply:**
- Trace without the setuid binary: run the sandbox as root and drop `sudo` from the traced command, or record reads another way, e.g. fanotify or atime.
- Or class sudo pairs as not runnable up front.
- In any effect comparison, count the pairs where **both runs failed** and report them apart: "nothing changed on either side" is weak evidence of equivalence.
