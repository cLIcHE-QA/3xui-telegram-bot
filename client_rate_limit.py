from __future__ import annotations

from collections import OrderedDict, deque
import time


DEFAULT_MAX_KEYS = 4096


class SlidingWindowRateLimiter:
    def __init__(
        self, *, limit: int, window_seconds: float, max_keys: int = DEFAULT_MAX_KEYS
    ):
        self.limit = max(1, int(limit))
        self.window_seconds = max(1.0, float(window_seconds))
        self.max_keys = max(1, int(max_keys))
        self._events: OrderedDict[int, deque[float]] = OrderedDict()

    def _expire_idle(self, cutoff: float) -> None:
        # Last accepted timestamps follow the trusted monotonic clock. Denials
        # and inspections never reorder users or prolong their retention.
        while self._events:
            oldest = next(iter(self._events.values()))
            if oldest[-1] > cutoff:
                break
            self._events.popitem(last=False)

    def allow(self, key: int, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        cutoff = current - self.window_seconds
        self._expire_idle(cutoff)
        normalized_key = int(key)
        bucket = self._events.get(normalized_key)
        if bucket is None:
            # Never evict a live user's window: doing so would reset their
            # budget. Capacity pressure uses the existing fail-closed refusal.
            if len(self._events) >= self.max_keys:
                return False
            bucket = deque()
            self._events[normalized_key] = bucket
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(current)
        self._events.move_to_end(normalized_key)
        return True

    def has_bucket(self, key: int) -> bool:
        """Check whether this in-process user has any unexpired limiter events."""
        cutoff = time.monotonic() - self.window_seconds
        self._expire_idle(cutoff)
        bucket = self._events.get(int(key))
        if not bucket:
            return False
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if not bucket:
            self._events.pop(int(key), None)
            return False
        return True

    def reset(self, key: int) -> None:
        self._events.pop(int(key), None)
