# GateProbe demo video — storyboard (W6)

**Target: 4:00 (CFP: 3–5 minutes).** The tool running, not slides: a terminal
(large font, light theme), a browser with the HTML report, and a Claude Code
session. Voice-over: `video/voiceover.md`. Captions: `video/captions.srt`, timed
to the same cues. Every shot runs from the **replay cache** (`--replay-only` /
`gateprobe replay`), so nothing depends on a live API on camera and no key is
ever loaded.

| # | Time | Shot | On screen | Depends on |
|---|---|---|---|---|
| 1 | 0:00–0:20 | Title | "GateProbe — metamorphic testing for coding-agent permission gates", authors, repo URL | H5 (URL) |
| 2 | 0:20–0:45 | The problem | A Claude Code session where a gate silently approves a call. Overlay: the call, "auto-approved by a learned gate" | — |
| 3 | 0:45–1:10 | The idea | The relations table from the paper, one row highlighted at a time (E, M, I, A, P), each with a concrete before/after call | — |
| 4 | 1:10–1:45 | Generate and run | Terminal: `gateprobe expand` (counts table scrolls), then `gateprobe replay --gate jev --variants variants/generated.jsonl --run-id demo` (counts appear) | X1 cache |
| 5 | 1:45–2:35 | The report | Browser: `gateprobe report` output. Pan over the floor table, then the flip table: red cells are violations, with intervals and R. Open one top-20 example: parent left, variant right | X4 (frozen runs) |
| 6 | 2:35–2:55 | Case study 1 | The report's before/after box: a destructive call auto-approved after an E or P rewrite. Zoom on the two p_block values | **X5** |
| 7 | 2:55–3:15 | CI mode | Terminal: `gateprobe ci --runs runs/demo.jsonl --max-flip 0.05` prints FAIL lines and exits 1; then the same check in a GitHub Actions log | X4 |
| 8 | 3:15–3:45 | Live hook (case study 2) | Claude Code with `gateprobe hook --replay-only` installed. The agent proposes the scripted call; the session shows the hook's verdict, its p_block, and the "⚠ fragile here" line | I2, **X5** |
| 9 | 3:45–4:00 | Close | Docker one-liner and replay command; repo, image and report URLs; "no API key needed to reproduce" | H5 |

**Case-study shots (6, 8) use only what X5 finds in the frozen runs.** If a case
doesn't occur, cut the shot and add time to shot 5 (the report). Never stage a
result that isn't in the data. Shot 8 follows the plan's fallback: if the hook
is flaky on camera, record it Thursday against the cached gate. If that fails
too, cut to a CLI-only version of the same call
(`echo '{...}' | gateprobe hook ...`).

## Pre-recording checklist

- [ ] Fresh terminal profile: no shell history, no prompt showing user or host names, large font.
- [ ] `.env` is **not** sourced. Run everything with `--replay-only` / `gateprobe replay`, and check with `env | grep -i key` (must print nothing) before recording.
- [ ] No API keys, tokens or `.env` contents anywhere on screen: editor tabs, browser tabs, notifications.
- [ ] Claude Code: a scratch project whose `.claude/settings.json` has only the GateProbe hook. Notifications are off.
- [ ] The replay cache holds every call the video shows: rehearse the whole script once with the network off.
- [ ] Browser zoom 125%, report opened from `reports/`, no other tabs.
- [ ] Screen resolution 1920×1080, recorded at 30 fps. Do mouse movements slowly.
- [ ] Captions: burn in, or upload `captions.srt` to YouTube. Check the timing after the edit.
- [ ] Upload unlisted to YouTube (H6). Paste the URL into `paper/main.tex` (`\videourl`) and the HotCRP abstract (W7).
