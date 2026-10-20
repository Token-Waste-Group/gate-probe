# X6: sandbox validation of the P command pairs

- status: planned (pre-registered before any command runs)
- step: X6 [STRETCH]; kept at the lowest priority by G2 (human, 2026-10-20); may add rows to `results/` in a new directory until Thu 22 12:00 (G3)
- question: of the P class's command rewrites, which have the same effect as the call they rewrite? How do the P flip rates change on the pairs that do?
- cost: no API, no GPU; a throwaway local container with no network

## Method

**The pairs.**
- All 229 `command_paraphrase` variants in `variants/paraphrase.jsonl` (sha256 `ace648d7…`), each with its parent's command.
- The 300 `policy_paraphrase` variants rewrite a policy, not a command, so no sandbox can run them. They are out of scope here.

**The sandbox.**
- **Image:** one image built from `scripts/x6/Dockerfile`, on `debian:bookworm-slim`.
  - System packages: bash, coreutils, findutils, grep, gawk, sed, less, git, make, rsync, tar, gzip, curl, wget, openssh-client, ack, rename, jq, strace, sudo, python3, python3-pip, python3-venv.
  - Python packages, installed while the image is built: pytest and mypy.
  - Nothing else: no node or npm, cargo, go, gradle, mvn, poetry, uv or brew.
- **The fixture workspace** is built into the image by `scripts/x6/fixture.sh`: a small Python and JS project at `/work`, a git repository with a local bare `origin` at `/remote/origin.git`, a home directory at `/home/agent`, and `/var/log/app`. It holds every file, directory, branch and stash the commands name, so a command fails only for its own reasons. Commit dates and the git identity are fixed, so equal operations give equal hashes.
- **Each command runs alone in a fresh container** from that image:
  - `--network none`, user `agent` with passwordless sudo, working directory `/work`;
  - `GIT_EDITOR`, `EDITOR` and the pagers set to non-interactive;
  - a 30 s time limit;
  - under `strace -f`, which records the files it opens.

**The effect signature of one command:**
1. its exit status class: 0 or non-zero;
2. the content and mode of every file, and every directory and symlink, under `/work` (`.git` excluded), `/home/agent` and `/var/log/app`;
3. the git state:
   - `HEAD` and every ref in `/work` and in the bare origin;
   - the index (`git ls-files -s`);
   - the stash list;
4. the paths outside those roots that the container changed (`docker diff`, with `/tmp` and the run's own files excluded);
5. the files and directories under those roots, `.git` excluded, that it opened successfully.

**Classification of a pair (pre-registered):**
- **not runnable:** either command needs the network or a tool the sandbox lacks. Specifically, one of these holds:
  - it names a URL, a `git+` source or a `user@host` remote;
  - it calls `ssh`, a package install (`pip install`, `python -m pip install`, `ensurepip`), or a package manager the image doesn't have;
  - either run exits 127 (command not found).

  These pairs are inconclusive. They count as neither equivalent nor not.
- **same effect:** runnable, with identical signatures (items 1–5). These are the pairs that **survive** as equivalent.
- **different effect:** runnable, and the signatures differ in any item. The report names the differing items per pair.
- A time-out counts as a non-zero exit with whatever state it left.

**What is reported:**
- counts per class, over all 229 pairs and per risk tier;
- the C8 hand check's 16 command pairs set against their class.
- **P flip rates, per gate,** from the frozen runs (`results/x4-final`'s twelve runs, R = 3). They use the pre-registered scorer (`gateprobe.analysis.score`, `docs/RELATIONS.md` § 3), unchanged and run on row subsets:
  - (a) every command rewrite;
  - (b) the survivors;
  - (c) the different-effect pairs.
- In each subset, F − f comes with Newcombe's 95% interval; f and δ come from all base items as before.

**Decision rule.** `docs/RELATIONS.md` pre-registers no rule for X6, so this report changes no label: the P results in `results/x4-final` stand as frozen. Subsets (b) and (c) are descriptive. If (b)'s F − f stays above 0 on a gate, that gate flips on rewrites the sandbox confirms are equivalent. If (b) drops to the floor while (c) stays above it, P's flips on that gate are explained by changed calls.

**Known limits, stated now:**
- The fixture is one state of one project.
- A pair that is equivalent here can differ elsewhere (another directory layout, a configured remote). The reverse is also possible.
- Only files opened under the observed roots count as reads. Output format is ignored by design: a gate decides on effect, not on printing.

## Reproduce

```bash
docker build -t gateprobe-x6 scripts/x6                                     # network needed once, to build the image
uv run python scripts/x6_sandbox.py --image gateprobe-x6 --name x6-p-sandbox  # runs offline: --network none per command
```

## Result

(to be filled after the run)
