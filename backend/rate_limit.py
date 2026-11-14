"""Een eenvoudige rem op het aantal aanvragen per adres.

In het geheugen van dit ene proces: genoeg om een losgeslagen script af te
remmen, geen vervanging voor bescherming bij de hoster.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, per_minute: int, window: float = 60.0, max_keys: int = 10_000):
        self.per_minute = per_minute
        self.window = window
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        """Telt deze aanvraag mee en zegt of hij nog binnen de limiet valt."""
        if self.per_minute <= 0:
            return True
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.per_minute:
            return False
        hits.append(now)
        if len(self._hits) > self.max_keys:
            self._forget_idle(now)
        return True

    def _forget_idle(self, now: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= self.window]:
            del self._hits[key]
