import time
import threading
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rpm: int):
        self.rpm = rpm
        self._lock = threading.Lock()
        self._tokens = rpm
        self._last_refill = time.monotonic()
        self._interval = 60.0 / rpm  # seconds between requests

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            # refill tokens based on elapsed time
            refill = elapsed * (self.rpm / 60.0)
            self._tokens = min(self.rpm, self._tokens + refill)
            self._last_refill = now

            if self._tokens >= 1:
                self._tokens -= 1
            else:
                wait = self._interval - elapsed
                if wait > 0:
                    logger.debug(f"Rate limit: sleeping {wait:.1f}s")
                    time.sleep(wait)
                self._tokens = 0
                self._last_refill = time.monotonic()
