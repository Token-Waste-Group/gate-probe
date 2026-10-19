# GateProbe demo video — voice-over (W6)

About 520 words, for a 4:00 video at a calm pace. Cue numbers match
`storyboard.md` and `captions.srt`. Bracketed numbers come from the frozen
runs (G3/X5) and are filled in before recording.

**1 · Title (0:00)**
GateProbe tests the permission gates that decide what a coding agent may do.

**2 · The problem (0:20)**
Every time a coding agent wants to run a command, edit a file or call the
network, a permission gate allows it, denies it, or asks you. More and more
often, that gate is a learned model: a decision model behind an API, or an
LLM acting as a judge. These gates sit in a security-critical place, and they
are rarely tested.

**3 · The idea (0:45)**
GateProbe tests a gate without needing the right answers. It rewrites a call
in ways whose effect on the verdict we know in advance. Writing a flag in its
long form must not change the verdict. Widening a deletion from the build
folder to the whole disk must not make the gate more willing. A timestamp or
a friendly remark must not move it, and neither should a claim that the user
already approved.

**4 · Generate and run (1:10)**
Here we expand our tool calls into about three thousand variants, then replay
the recorded answers of Jev, a typed decision model. Every answer came from
three separate calls, so we can measure how much the gate disagrees with
itself.

**5 · The report (1:45)**
That self-disagreement is the noise floor. The report counts a relation as
violated only when flips rise above that floor, beyond the interval. Red cells
are violations. Here, [relation] flips [x] points more often than the gate
disagrees with itself. Every cell shows its interval and the number of
repeats. Opening one example puts the original call next to the rewrite.

**6 · Case study (2:35)**
This one is a destructive command. Written one way, the gate blocks it.
Written an equivalent way, it lets it through: the block probability falls
from [a] to [b].

**7 · CI mode (2:55)**
A team that ships a gate can fail its build on this. The check fails only
when the excess is significant and larger than the threshold you set, so
noise alone never breaks the build.

**8 · Live hook (3:15)**
GateProbe also plugs into Claude Code. As the agent works, the hook shows what
the gate would decide for each real call, and warns when the call has a
feature the gate is known to be fragile on. It never approves anything by
itself.

**9 · Close (3:45)**
Everything in this video replays from the published cache, inside the Docker
image, with no API key. The links are below.
