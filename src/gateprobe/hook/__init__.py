"""The live Claude Code PreToolUse hook: sends a real tool call to the gate under
test and prints its verdict, with a warning when a known-fragile relation applies.

Scope of v0: package marker only. Out of scope (later steps): the hook (I2) and
the optional OpenCode plugin (I7, stretch).
"""
