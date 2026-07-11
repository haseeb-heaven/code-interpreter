"""Unit tests for libs.rate_limiter.TokenBucket."""

from __future__ import annotations

import threading
import time
import unittest

from libs.rate_limiter import RateLimitExceeded, TokenBucket


class TestTokenBucket(unittest.TestCase):
	def test_invalid_capacity_and_refill(self):
		with self.assertRaises(ValueError):
			TokenBucket(capacity=0, refill_rate=1.0)
		with self.assertRaises(ValueError):
			TokenBucket(capacity=1.0, refill_rate=0)

	def test_bucket_starts_full(self):
		bucket = TokenBucket(capacity=5.0, refill_rate=1.0)
		for _ in range(5):
			self.assertTrue(bucket.try_acquire())
		self.assertFalse(bucket.try_acquire())

	def test_bucket_blocks_when_empty(self):
		bucket = TokenBucket(capacity=1.0, refill_rate=20.0)  # 20 tokens/s
		self.assertTrue(bucket.try_acquire())
		started = time.monotonic()
		bucket.acquire(timeout=1.0)
		elapsed = time.monotonic() - started
		# Needed ~0.05s for one token at 20/s; allow generous jitter
		self.assertGreaterEqual(elapsed, 0.02)
		self.assertLess(elapsed, 0.8)

	def test_try_acquire_returns_false_when_empty(self):
		bucket = TokenBucket(capacity=1.0, refill_rate=0.01)
		self.assertTrue(bucket.try_acquire())
		started = time.monotonic()
		self.assertFalse(bucket.try_acquire())
		self.assertLess(time.monotonic() - started, 0.05)

	def test_refill_rate_accuracy(self):
		bucket = TokenBucket.from_rpm(rpm=60.0, burst=1)
		self.assertTrue(bucket.try_acquire())
		self.assertFalse(bucket.try_acquire())
		time.sleep(1.05)
		# ~1 token/s refill after draining capacity-1
		self.assertGreaterEqual(bucket.tokens, 0.9)
		self.assertLessEqual(bucket.tokens, 1.15)
		self.assertTrue(bucket.try_acquire())

	def test_burst_then_throttle(self):
		bucket = TokenBucket(capacity=5.0, refill_rate=2.0)
		for _ in range(5):
			self.assertTrue(bucket.try_acquire())
		self.assertFalse(bucket.try_acquire())
		started = time.monotonic()
		bucket.acquire(timeout=1.0)
		elapsed = time.monotonic() - started
		self.assertGreaterEqual(elapsed, 0.3)  # need 0.5s at 2/s; allow early wake

	def test_acquire_timeout_raises(self):
		bucket = TokenBucket(capacity=1.0, refill_rate=0.01)
		self.assertTrue(bucket.try_acquire())
		with self.assertRaises(RateLimitExceeded):
			bucket.acquire(timeout=0.05)

	def test_thread_safe_concurrent_consumption(self):
		# Capacity covers all planned acquires; assert tokens never go negative.
		bucket = TokenBucket(capacity=50.0, refill_rate=100.0)
		errors = []
		acquired = []

		def worker():
			try:
				for _ in range(5):
					ok = bucket.try_acquire()
					if ok:
						acquired.append(1)
						# Snapshot under lock via property (refills first)
						if bucket.tokens < -1e-9:
							errors.append(f"negative tokens: {bucket.tokens}")
					else:
						# Wait briefly then retry once
						bucket.acquire(timeout=0.5)
						acquired.append(1)
			except Exception as exc:  # noqa: BLE001
				errors.append(exc)

		threads = [threading.Thread(target=worker) for _ in range(10)]
		for t in threads:
			t.start()
		for t in threads:
			t.join(timeout=10)
		self.assertEqual(errors, [])
		self.assertEqual(len(acquired), 50)
		self.assertGreaterEqual(bucket.tokens, 0.0)

	def test_custom_rpm_config(self):
		bucket = TokenBucket.from_rpm(rpm=120.0, burst=1)
		self.assertAlmostEqual(bucket.refill_rate, 2.0, places=5)
		self.assertTrue(bucket.try_acquire())
		time.sleep(0.55)
		# ~2 tokens/s → ~1.1 tokens after 0.55s
		self.assertGreaterEqual(bucket.tokens, 0.9)
		self.assertLessEqual(bucket.tokens, 1.3)


if __name__ == "__main__":
	unittest.main()
