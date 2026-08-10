"""
Thread-safe adaptive token-bucket rate limiter.

Adapted from the project's existing GraphRateLimiter pattern.

Behavior:
- acquire() blocks until a request token is available.
- notify_throttled() halves the current rate, down to min_rate.
- notify_success() gradually increases the rate back toward max_rate.
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """
    Thread-safe adaptive token-bucket rate limiter.

    Example:
        limiter = RateLimiter(rate_per_second=5.0)

        limiter.acquire()

        try:
            response = make_request()

            if response.status_code == 429:
                limiter.notify_throttled()
            elif response.ok:
                limiter.notify_success()

        except Exception:
            raise
    """

    def __init__(
        self,
        rate_per_second: float,
        min_rate: float = 1.0,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be greater than 0")

        if min_rate <= 0:
            raise ValueError("min_rate must be greater than 0")

        if min_rate > rate_per_second:
            raise ValueError(
                "min_rate cannot be greater than rate_per_second"
            )

        self._initial_rate = float(rate_per_second)
        self._max_rate = float(rate_per_second)
        self._min_rate = float(min_rate)

        self._rate = float(rate_per_second)
        self._tokens = float(rate_per_second)

        self._lock = threading.Lock()
        self._last_ts = time.monotonic()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time.

        Must be called while holding self._lock.
        """
        now = time.monotonic()
        delta = now - self._last_ts
        self._last_ts = now

        self._tokens = min(
            self._rate,
            self._tokens + delta * self._rate,
        )

    def acquire(self) -> None:
        """Block until one request token is available."""
        while True:
            with self._lock:
                self._refill()

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

            # Same low-cost polling approach as the original implementation.
            time.sleep(0.02)

    def notify_throttled(self) -> None:
        """Tell the limiter that the service throttled us.

        The current request rate is cut in half, but never below min_rate.
        """
        with self._lock:
            self._rate = max(
                self._min_rate,
                self._rate * 0.5,
            )

            # Keep the existing token count valid for the new bucket size.
            self._tokens = min(self._tokens, self._rate)

            current_rate = self._rate

        print(
            f"[rate-limiter] Throttled -> "
            f"rate reduced to {current_rate:.2f} req/s"
        )

    def notify_success(self) -> None:
        """Tell the limiter that a request succeeded.

        Gradually recover toward the original maximum rate.
        """
        with self._lock:
            self._rate = min(
                self._max_rate,
                self._rate * 1.05,
            )

    @property
    def current_rate(self) -> float:
        """Return the current requests-per-second rate."""
        with self._lock:
            return self._rate