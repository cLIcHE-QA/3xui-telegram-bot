from __future__ import annotations

from collections import defaultdict, deque
import time


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: float):
        self.limit = max(1, int(limit))
        self.window_seconds = max(1.0, float(window_seconds))
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, key: int, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        cutoff = current - self.window_seconds
        bucket = self._events[int(key)]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(current)
        return True

    def reset(self, key: int) -> None:
        self._events.pop(int(key), None)
