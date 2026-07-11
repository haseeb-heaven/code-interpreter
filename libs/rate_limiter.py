"""Token-bucket rate limiter for per-key LLM request throttling."""
from __future__ import annotations

import threading
import time
from typing import Optional


class RateLimitExceeded(Exception):
	"""Raised when acquire() times out waiting for a token."""


class TokenBucket:
	"""Thread-safe token bucket.

	``capacity`` is the max burst size.
	``refill_rate`` is tokens per second (RPM / 60).
	"""

	def __init__(self, capacity: float = 10.0, refill_rate: float = 1.0):
		if capacity <= 0:
			raise ValueError("capacity must be > 0")
		if refill_rate <= 0:
			raise ValueError("refill_rate must be > 0")
		self.capacity = float(capacity)
		self.refill_rate = float(refill_rate)
		self._tokens = float(capacity)
		self._updated_at = time.monotonic()
		self._lock = threading.Lock()

	def _refill(self) -> None:
		now = time.monotonic()
		elapsed = now - self._updated_at
		if elapsed > 0:
			self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
			self._updated_at = now

	@property
	def tokens(self) -> float:
		with self._lock:
			self._refill()
			return self._tokens

	def try_acquire(self, tokens: float = 1.0) -> bool:
		with self._lock:
			self._refill()
			if self._tokens >= tokens:
				self._tokens -= tokens
				return True
			return False

	def acquire(self, timeout: Optional[float] = None, tokens: float = 1.0) -> None:
		"""Block until ``tokens`` are available or raise RateLimitExceeded."""
		deadline = None if timeout is None else (time.monotonic() + float(timeout))
		while True:
			with self._lock:
				self._refill()
				if self._tokens >= tokens:
					self._tokens -= tokens
					return
				needed = tokens - self._tokens
				wait = needed / self.refill_rate if self.refill_rate > 0 else 0.05
			if deadline is not None:
				remaining = deadline - time.monotonic()
				if remaining <= 0:
					raise RateLimitExceeded("Token bucket acquire timed out")
				wait = min(wait, remaining)
			time.sleep(max(wait, 0.001))

	@classmethod
	def from_rpm(cls, rpm: float = 60.0, burst: int = 10) -> "TokenBucket":
		return cls(capacity=float(burst), refill_rate=float(rpm) / 60.0)
