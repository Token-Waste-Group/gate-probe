"""Sends variants x repeats through a gate adapter, with retries, a
content-addressed response cache (which is also the replay mode) and the
per-gate $ cap.

Scope of v0: `cache` (the content-addressed store) and `run` (the run loop,
provenance, spend log). Out of scope (later steps): Message Batches submission
for the Claude judge (R8).
"""
