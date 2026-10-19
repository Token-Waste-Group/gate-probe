"""The HTTP transport the API-backed adapters share: a stdlib JSON POST,
injectable so tests never touch the network.

Scope of v0: one POST returning (status, parsed body), network failures as a
retryable `GateHTTPError`, and the set of retryable statuses. Out of scope:
retries themselves (the runner) and streaming.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

RETRYABLE = frozenset({408, 429, 500, 502, 503, 524, 529})

# (url, headers, body) -> (HTTP status, parsed JSON body)
Transport = Callable[[str, dict[str, str], dict[str, Any]], tuple[int, dict[str, Any]]]


class GateHTTPError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = status in RETRYABLE or status is None  # None: network-level failure


def urllib_transport(timeout_s: float = 60.0) -> Transport:
    def send(url: str, headers: dict[str, str], body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read() or b"{}")
            except json.JSONDecodeError:
                payload = {}
            return e.code, payload
        except (urllib.error.URLError, TimeoutError) as e:
            raise GateHTTPError(f"network error: {e.__class__.__name__}") from e

    return send
