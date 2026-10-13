"""Bounded per-process limits for the single-worker deployment."""
import time
from collections import OrderedDict, deque
from threading import Lock
from fastapi import HTTPException

class RequestLimiter:
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = Lock()

    def check(self, key, count, window=60):
        now = time.monotonic()
        with self.lock:
            q = self.entries.setdefault(key, deque())
            self.entries.move_to_end(key)
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= count:
                raise HTTPException(429, "请求过于频繁，请稍后重试", headers={"Retry-After": str(window)})
            q.append(now)
            while len(self.entries) > 10000:
                self.entries.popitem(last=False)

limiter = RequestLimiter()
