"""Metamorphic relation generators. Every variant carries its parent id, its class
(E, M, I, A or P), its transform and its expected outcome.

Scope of v0: `common` (tokens, seeds, the variant builder), the deterministic
classes `equivalence` and `irrelevance` (C4), `monotonicity` and `adversarial`
(C5), and `expand` (`gateprobe expand`). Out of scope (later steps): the P
paraphrase class (C8). No relation class beyond E/M/I/A/P, ever (frozen at G1).
"""
