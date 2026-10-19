"""Sends variants x repeats through a gate adapter, with retries, a
content-addressed response cache (which is also the replay mode) and the
per-gate $ cap.

Scope of v0: package marker only. Out of scope (later steps): the runner, cache,
replay and spend log (R2); Message Batches submission for the Claude judge (R8).
"""
