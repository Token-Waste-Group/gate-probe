# The Gemma 4 judge on vLLM (R5)

`compose.yaml` serves `google/gemma-4-31B-it` for the `judge-gemma` gate on the
H100 node (`ssh d.dgx`). The rules are in `memory/reference-dgx-usage.md`:
- GPU 7 only;
- docker compose only, nothing installed on the host;
- every file under `/data/storage/kaluzhnaya_jhub/gate-probe/vllm-judge/`;
- never stop `kaluzhnaya_stale_runner`.

## What is served

| | |
|---|---|
| model | `google/gemma-4-31B-it`, served under that name (the adapter rejects any other) |
| revision | `842da3794eaa0b77d5f08bae87a17459d91ff475` (Hugging Face commit of 2026-07-20; not gated) |
| dtype | bfloat16, the checkpoint's own: 62.5 GB of weights, no quantization |
| server | `vllm/vllm-openai:v0.29.0` (vLLM 0.29.0, transformers 5.16.1), already on the host |
| flags | `--language-model-only`, `--generation-config=vllm`, `--max-model-len=8192`, `--max-logprobs=20`, `--gpu-memory-utilization=0.95`, `--seed=0` |
| port | `127.0.0.1:8017` on the host, so only reachable through an ssh tunnel |

Why the flags:
- `--language-model-only`: the prompts are text, so the vision and audio encoders are not loaded.
- `--generation-config=vllm`: the checkpoint's `generation_config.json` sets top_k 64 and top_p 0.95 as sampling defaults. This flag keeps them out. The adapter sends temperature 0.
- The chat template leaves thinking off unless a request turns it on, and the adapter never does. So the first generated token is the answer, which is where the adapter reads its logprobs.

**The weight fit.** bf16 needs the whole GPU: 62.5 GB of weights at 0.95 of 80 GB leaves about 13 GB for the KV cache. That works only while GPU 7 is free. On 2026-10-20 it was (4 MiB used) and `kaluzhnaya_stale_runner` was not running. If that container holds GPU 7 again, its ~40 GB share doesn't fit these weights. Then don't stop it: block the step and ask (an FP8 checkpoint would be a different gate).

## Bring-up

The storage directory is root-owned, so every file operation runs inside a container. The compose file goes over ssh by process substitution, so nothing lands outside storage.

```bash
B64=$(base64 < deploy/vllm-judge/compose.yaml | tr -d '\n')
DC="docker compose -p gateprobe-judge -f <(echo $B64 | base64 -d)"

ssh d.dgx nvidia-smi -i 7                                   # occupancy first: GPU 7 must be free
ssh d.dgx "bash -c '$DC --profile stage run --rm stage'"    # once: the pinned weights into the HF cache
ssh d.dgx "bash -c '$DC up -d judge'"                       # serves offline from that cache
ssh d.dgx "docker logs -f gateprobe-judge-judge-1"          # wait for "Application startup complete"
ssh -N -L 8017:127.0.0.1:8017 d.dgx &                       # the tunnel; the gate's base_url is localhost:8017
curl -s localhost:8017/v1/models                            # lists google/gemma-4-31B-it
```

The bind-mount source must exist before the first `run`. Create it with any container that mounts the parent `/data/storage/kaluzhnaya_jhub` (`mkdir -p .../gate-probe/vllm-judge/hf`).

Smoke test through the adapter: 10 corpus items, one repeat. It uses a scratch run config, so the frozen `results/spend.csv` and `cache/` stay untouched:

```bash
sed -e 's#^cache_dir:.*#cache_dir: /tmp/r5-smoke/cache#' -e 's#^runs_dir:.*#runs_dir: /tmp/r5-smoke/runs#' \
    -e 's#^spend_csv:.*#spend_csv: /tmp/r5-smoke/spend.csv#' configs/run.yaml > /tmp/r5-smoke/run.yaml
uv run gateprobe run --gate judge-gemma --variants variants/generated.jsonl --limit 10 --repeats 1 \
    --run-id r5-smoke --run-config /tmp/r5-smoke/run.yaml
```

## Teardown

```bash
ssh d.dgx "bash -c '$DC down'"                              # stops and removes the server container
```

When X2's rows and report are in, delete the weights. Use a container again, since the directory is root-owned:

```bash
ssh d.dgx "bash -c '$DC --profile stage run --rm --entrypoint rm stage -rf /store/hf'"
```

The `vllm/vllm-openai:v0.29.0` image was on the host before this step. Leave it.
