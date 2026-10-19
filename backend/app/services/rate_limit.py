"""Per-client request limit for endpoints that cost money or database time.

A sliding window in memory: simple, and enough for a single server process.
Running several processes would need a shared store such as Redis.
"""
import math
import threading
import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> int | None:
        """Record a request. Returns None if allowed, else seconds to wait."""
        if self._limit <= 0:
            return None
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return max(1, math.ceil(self._window - (now - hits[0])))
            hits.append(now)
            if len(self._hits) > 10_000:
                self._forget_idle(now)
            return None

    def _forget_idle(self, now: float) -> None:
        idle = [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= self._window]
        for key in idle:
            del self._hits[key]
