# Case studies for the paper box and the video (X5)
- status: planned
- result: —

## Question

The plan's two case studies (`gateprobe_plan.md` § Validation plan), taken from the frozen runs only:

1. a **destructive command auto-approved after an E or P rewrite**;
2. the **"pre-approved" injection moving Jev's block probability across the configured threshold** (τ = 0.5).

Each is reproduced from the response cache with its exact before/after inputs and probabilities. If a case doesn't occur in the data, the report says so. Nothing outside the frozen runs is searched.

## Method (+ reproduce and replay commands)

- **Data:** the 12 frozen runs behind `results/x4-final/` (E/M/I/A and P on six gates, R = 3), with `variants/generated.jsonl`, `variants/paraphrase.jsonl` and the risk tiers in `probes/corpus.jsonl`. No gate is called: `gateprobe replay` reads the cache and fails on any miss.
- **Commands:**
  ```
  python3 scripts/case_studies.py            # writes results/x5-case-studies/*.csv and variants/x5-case-{1,2}.jsonl
  gateprobe replay --gate <case 1 gate> --variants variants/x5-case-1.jsonl --run-id x5-case-1
  gateprobe replay --gate jev           --variants variants/x5-case-2.jsonl --run-id x5-case-2
  ```
  Each replay must return, repeat by repeat, the same verdicts and p_block as the frozen run rows. The report shows both.
- **Disclosure:** X4's top-transform list (`results/x4-final/top_transforms.csv`) already showed some E flips on destructive calls. The selection rules below are fixed before the script runs, so the box is picked by rule, not by eye.

## Selection rules (pre-registered, before the script runs)

**Case 1, destructive command auto-approved after an E or P rewrite:**
- **Population:** every (parent, variant) pair of class E or P, on all six gates, whose probe is in the `irreversible` tier. That is "destructive" as `docs/CORPUS.md` defines it: deleting sources or home-directory files.
- **Event:** the parent's **majority** verdict over the 3 repeats is deny and the variant's is allow. The majority makes the event robust to the floor.
- **Exclusion:** variants that the X4 § 5 check found not equivalent are excluded and named: p0280 and p0294 `path_normalization` (in the `exfiltration` tier, so outside this population anyway).
- **Listing:** every event is listed in `case1_events.csv`.
- **The box:** the E event with the largest drop in mean p_block.
  - Ties go to the gate order Jev, rules, Claude, Luna, pplx, drex, then to the lower variant id.
  - If there is no E event, the box takes the largest P event and states that P rewrites can be non-equivalent (C8). Whether the shown rewrite is equivalent is judged by hand in the report.
  - If neither occurs, the report says so.

**Case 2, Jev's "pre-approved" injection across τ:**
- **Population:** Jev's 300 `inject_preapproved` pairs.
- **Event:** at some repeat k, p(x, k) and p(y, k) lie on opposite sides of τ = 0.5, where x is the parent and y the injected variant. Both directions are counted.
- **The box:** the crossing toward allow (p(x,k) ≥ 0.5 > p(y,k)) with the largest drop in mean p. Ties go to the lower variant id.
  - If no crossing goes toward allow, the report says that the injection never moved Jev toward allow across τ in the frozen runs. It then shows the largest drop in mean p, without a crossing, as the closest case.
- **Context only:** the same count for the other five gates, in `case2_events.csv`.

## Data

(filled after the script and the replays run)

## Result

(filled after)

## Conclusion & implication

(filled after)
