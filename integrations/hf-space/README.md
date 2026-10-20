---
title: GateProbe replay demo
emoji: 🚦
colorFrom: gray
colorTo: red
sdk: static
app_file: index.html
pinned: false
short_description: Browse metamorphic flips of six coding-agent permission gates
---

# GateProbe replay demo

A static page over the frozen GateProbe results:
- the flip-rate table, per gate and relation, with 95% intervals;
- the per-transform rates;
- every pair whose verdicts differ, with both inputs side by side.

Every answer was recorded in the frozen runs and comes from the replay bundle. The page never calls a gate and needs no key. It fetches nothing but `data.json`.

## Run it locally

```bash
python3 -m http.server -d integrations/hf-space 8000   # then open http://localhost:8000
```

In a fresh container:

```bash
docker run --rm -p 8000:8000 -v "$PWD/integrations/hf-space:/srv:ro" python:3.11-slim \
  python -m http.server -d /srv 8000
```

## Rebuild the data

`data.json` is distilled from the replay bundle, so it is never edited by hand. It holds:
- the frozen tables in `results/x4-final/`;
- every flipped pair, with verdict and `p_block` per repeat;
- the inputs the gate saw for both sides.

```bash
uv run python scripts/build_bundle.py --no-site      # dist/gateprobe-replay-19fd14a.tar.gz
uv run python integrations/hf-space/build_data.py --bundle dist/gateprobe-replay-19fd14a.tar.gz
```

Publishing the Space is a human step (H5). The Space repository takes four files from this directory: `README.md`, `index.html`, `app.js` and `data.json`.
