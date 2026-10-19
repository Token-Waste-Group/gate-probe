"""Tests for the video materials: well-formed captions within the CFP's 3-5 minutes, and the safety checklist.

Scope of v0: video/captions.srt and video/storyboard.md. Out of scope: the recording (H4, H6).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUE = re.compile(r"^(\d+)\n(\d\d):(\d\d):(\d\d),(\d{3}) --> (\d\d):(\d\d):(\d\d),(\d{3})\n(.+)$", re.DOTALL)


def seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def test_captions_are_sequential_ordered_and_within_three_to_five_minutes():
    blocks = (ROOT / "video" / "captions.srt").read_text(encoding="utf-8").strip().split("\n\n")
    last_end = 0.0
    for i, block in enumerate(blocks, start=1):
        m = CUE.match(block)
        assert m, block
        assert int(m.group(1)) == i
        start, end = seconds(*m.group(2, 3, 4, 5)), seconds(*m.group(6, 7, 8, 9))
        assert last_end <= start < end
        last_end = end
    assert 180 <= last_end <= 300


def test_storyboard_has_the_no_keys_checklist_and_marks_data_dependent_shots():
    text = " ".join((ROOT / "video" / "storyboard.md").read_text(encoding="utf-8").split())  # unwrap lines
    assert "--replay-only" in text and "No API keys" in text and ".env" in text
    assert "**X5**" in text and "Never stage a result" in text
