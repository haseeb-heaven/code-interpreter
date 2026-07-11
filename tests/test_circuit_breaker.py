"""Circuit-breaker lifecycle tests for KeyState / ProviderKeyPool."""

from __future__ import annotations

import time
import unittest

from libs.key_manager import CircuitState, KeyState, ProviderKeyPool


class TestCircuitBreaker(unittest.TestCase):
	def test_starts_closed(self):
		ks = KeyState(value="sk-test", index=0)
		self.assertEqual(ks.circuit_state, CircuitState.CLOSED)
		self.assertFalse(ks.is_circuit_open())

	def test_opens_after_threshold(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=3)
		ks.record_failure()
		ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.CLOSED)
		ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.OPEN)

	def test_blocks_when_open(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=2, circuit_cooldown=60.0)
		ks.record_failure()
		ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.OPEN)
		self.assertFalse(ks.is_available())
		self.assertTrue(ks.is_circuit_open())

	def test_half_open_after_cooldown(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=2, circuit_cooldown=0.05)
		ks.record_failure()
		ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.OPEN)
		time.sleep(0.08)
		self.assertFalse(ks.is_circuit_open())
		self.assertEqual(ks.circuit_state, CircuitState.HALF_OPEN)

	def test_closes_on_successful_probe(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=2, circuit_cooldown=0.05)
		ks.record_failure()
		ks.record_failure()
		time.sleep(0.08)
		self.assertFalse(ks.is_circuit_open())  # → HALF_OPEN
		ks.record_success()
		self.assertEqual(ks.circuit_state, CircuitState.CLOSED)
		self.assertTrue(ks.is_available())

	def test_reopens_on_failed_probe(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=2, circuit_cooldown=0.05)
		ks.record_failure()
		ks.record_failure()
		time.sleep(0.08)
		self.assertFalse(ks.is_circuit_open())
		self.assertEqual(ks.circuit_state, CircuitState.HALF_OPEN)
		before = time.time()
		ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.OPEN)
		self.assertGreaterEqual(ks.circuit_open_until, before + 0.04)
		self.assertTrue(ks.is_circuit_open())

	def test_full_lifecycle(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=2, circuit_cooldown=0.05)
		self.assertEqual(ks.circuit_state, CircuitState.CLOSED)
		ks.record_failure()
		ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.OPEN)
		time.sleep(0.08)
		self.assertFalse(ks.is_circuit_open())
		self.assertEqual(ks.circuit_state, CircuitState.HALF_OPEN)
		ks.record_success()
		self.assertEqual(ks.circuit_state, CircuitState.CLOSED)

	def test_configurable_threshold(self):
		pool = ProviderKeyPool("openai", ["k0"], circuit_threshold=5, circuit_cooldown=60.0)
		for _ in range(4):
			pool.record_failure(0)
		self.assertEqual(pool.keys()[0].circuit_state, CircuitState.CLOSED)
		pool.record_failure(0)
		self.assertEqual(pool.keys()[0].circuit_state, CircuitState.OPEN)

	def test_configurable_cooldown(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=1, circuit_cooldown=0.1)
		ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.OPEN)
		time.sleep(0.05)
		self.assertTrue(ks.is_circuit_open())
		time.sleep(0.07)  # total ~120ms > 100ms cooldown
		self.assertFalse(ks.is_circuit_open())
		self.assertEqual(ks.circuit_state, CircuitState.HALF_OPEN)


if __name__ == "__main__":
	unittest.main()
