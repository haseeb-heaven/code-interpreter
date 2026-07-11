"""Unit tests for libs.key_manager — KeyState, ProviderKeyPool, KeyManager."""

from __future__ import annotations

import threading
import time
import unittest
from collections import Counter
from unittest.mock import patch

from libs.key_manager import (
	CircuitState,
	ErrorClassifier,
	ErrorType,
	KeyManager,
	KeyState,
	MetricsLogger,
	ProviderKeyPool,
	provider_from_api_key_name,
)


class TestKeyState(unittest.TestCase):
	def test_initial_state_is_available(self):
		ks = KeyState(value="sk-test", index=0)
		self.assertTrue(ks.is_available())
		self.assertEqual(ks.circuit_state, CircuitState.CLOSED)
		self.assertEqual(ks.failures, 0)

	def test_record_success_clears_failures(self):
		ks = KeyState(value="sk-test", index=0)
		ks.failures = 2
		ks.record_success()
		self.assertEqual(ks.failures, 0)
		self.assertEqual(ks.successes, 1)
		self.assertEqual(ks.circuit_state, CircuitState.CLOSED)

	def test_rate_limit_makes_unavailable(self):
		ks = KeyState(value="sk-test", index=0)
		ks.record_failure(is_rate_limit=True, rate_limit_seconds=60.0)
		self.assertFalse(ks.is_available())
		self.assertGreater(ks.rate_limited_until, time.time())

	def test_rate_limit_expires(self):
		ks = KeyState(value="sk-test", index=0)
		ks.rate_limited_until = time.time() - 1.0
		self.assertTrue(ks.is_available())

	def test_circuit_opens_after_threshold(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=3)
		for _ in range(3):
			ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.OPEN)
		self.assertFalse(ks.is_available())

	def test_circuit_resets_after_duration(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=3, circuit_cooldown=120.0)
		for _ in range(3):
			ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.OPEN)
		ks.circuit_open_until = time.time() - 1.0
		# Past cooldown → HALF_OPEN probe allowed (available again)
		self.assertTrue(ks.is_available())
		self.assertEqual(ks.circuit_state, CircuitState.HALF_OPEN)

	def test_success_after_circuit_open_resets(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=3)
		for _ in range(3):
			ks.record_failure()
		self.assertEqual(ks.circuit_state, CircuitState.OPEN)
		ks.record_success()
		self.assertEqual(ks.circuit_state, CircuitState.CLOSED)
		self.assertEqual(ks.failures, 0)
		self.assertTrue(ks.is_available())


class TestProviderKeyPool(unittest.TestCase):
	def test_round_robin_rotation(self):
		pool = ProviderKeyPool("openai", ["k0", "k1", "k2"])
		seen = [pool.get_key().index for _ in range(6)]
		self.assertEqual(Counter(seen), {0: 2, 1: 2, 2: 2})

	def test_skips_rate_limited_key(self):
		pool = ProviderKeyPool("openai", ["k0", "k1", "k2"])
		pool.record_failure(0, is_rate_limit=True, rate_limit_seconds=120.0)
		for _ in range(10):
			ks = pool.get_key()
			self.assertIsNotNone(ks)
			self.assertIn(ks.index, (1, 2))

	def test_returns_none_when_all_unavailable(self):
		pool = ProviderKeyPool("openai", ["k0"])
		pool.record_failure(0, is_rate_limit=True, rate_limit_seconds=120.0)
		self.assertIsNone(pool.get_key())

	def test_record_success_updates_state(self):
		pool = ProviderKeyPool("openai", ["k0"])
		pool.record_failure(0)
		pool.record_failure(0)
		self.assertEqual(pool.keys()[0].failures, 2)
		pool.record_success(0)
		self.assertEqual(pool.keys()[0].failures, 0)
		self.assertEqual(pool.keys()[0].successes, 1)

	def test_record_failure_opens_circuit(self):
		pool = ProviderKeyPool("openai", ["k0"], circuit_threshold=3)
		for _ in range(3):
			pool.record_failure(0)
		self.assertEqual(pool.keys()[0].circuit_state, CircuitState.OPEN)
		self.assertIsNone(pool.get_key())

	def test_status_reflects_availability(self):
		pool = ProviderKeyPool("openai", ["k0", "k1"])
		pool.record_failure(0, is_rate_limit=True, rate_limit_seconds=120.0)
		rows = pool.status()
		by_idx = {r["index"]: r for r in rows}
		self.assertFalse(by_idx[0]["available"])
		self.assertTrue(by_idx[1]["available"])

	def test_available_count(self):
		pool = ProviderKeyPool("openai", ["k0", "k1", "k2"])
		pool.record_failure(0, is_rate_limit=True, rate_limit_seconds=120.0)
		self.assertEqual(pool.available_count(), 2)

	def test_thread_safety(self):
		pool = ProviderKeyPool("openai", [f"k{i}" for i in range(5)])
		errors = []
		results = []

		def worker():
			try:
				for _ in range(50):
					ks = pool.get_key()
					if ks is None:
						errors.append("got None")
						return
					results.append(ks.index)
			except Exception as exc:  # noqa: BLE001 — collect for assertion
				errors.append(exc)

		threads = [threading.Thread(target=worker) for _ in range(10)]
		for t in threads:
			t.start()
		for t in threads:
			t.join(timeout=10)
		self.assertEqual(errors, [])
		self.assertEqual(len(results), 500)
		self.assertTrue(all(isinstance(i, int) for i in results))

	def test_empty_keys_raises(self):
		with self.assertRaises(ValueError):
			ProviderKeyPool("openai", [])


class TestKeyManager(unittest.TestCase):
	def setUp(self):
		KeyManager.reset_singleton()

	def tearDown(self):
		KeyManager.reset_singleton()

	def _env(self, mapping):
		def getenv(name, default=None):
			return mapping.get(name, default)

		return getenv

	def test_discovers_bare_key(self):
		km = KeyManager(getenv_fn=self._env({"OPENAI_API_KEY": "sk-bare"}))
		pool = km.get_pool("openai")
		self.assertIsNotNone(pool)
		self.assertEqual(pool.size, 1)
		self.assertEqual(pool.keys()[0].value, "sk-bare")

	def test_discovers_numbered_keys(self):
		env = {
			"OPENAI_API_KEY_1": "sk-1",
			"OPENAI_API_KEY_2": "sk-2",
			"OPENAI_API_KEY_3": "sk-3",
		}
		km = KeyManager(getenv_fn=self._env(env))
		pool = km.get_pool("openai")
		self.assertEqual(pool.size, 3)
		self.assertEqual([k.value for k in pool.keys()], ["sk-1", "sk-2", "sk-3"])

	def test_numbered_keys_take_precedence_over_bare(self):
		env = {
			"OPENAI_API_KEY": "sk-bare",
			"OPENAI_API_KEY_1": "sk-1",
			"OPENAI_API_KEY_2": "sk-2",
		}
		km = KeyManager(getenv_fn=self._env(env))
		values = [k.value for k in km.get_pool("openai").keys()]
		self.assertNotIn("sk-bare", values)
		self.assertEqual(values, ["sk-1", "sk-2"])

	def test_missing_provider_returns_none(self):
		km = KeyManager(getenv_fn=self._env({"OPENAI_API_KEY": "sk-only"}))
		self.assertIsNone(km.acquire_key("anthropic"))

	def test_record_success_clears_failure(self):
		km = KeyManager(getenv_fn=self._env({"OPENAI_API_KEY": "sk-test"}))
		ks = km.acquire_key("openai")
		km.record_failure("openai", ks.index)
		km.record_failure("openai", ks.index)
		km.record_success("openai", ks.index)
		pool = km.get_pool("openai")
		self.assertEqual(pool.keys()[ks.index].failures, 0)
		self.assertEqual(pool.keys()[ks.index].successes, 1)

	def test_record_failure_rate_limit(self):
		km = KeyManager(getenv_fn=self._env({"OPENAI_API_KEY": "sk-test"}))
		ks = km.acquire_key("openai")
		km.record_failure("openai", ks.index, is_rate_limit=True, rate_limit_seconds=90.0)
		self.assertFalse(km.get_pool("openai").keys()[0].is_available())
		self.assertGreater(
			km.get_pool("openai").keys()[0].rate_limited_until,
			time.time() + 60,
		)

	def test_reload_picks_up_new_keys(self):
		env = {"OPENAI_API_KEY_1": "sk-1"}
		km = KeyManager(getenv_fn=self._env(env))
		self.assertEqual(km.get_pool("openai").size, 1)
		env["OPENAI_API_KEY_2"] = "sk-2"
		km.reload()
		self.assertEqual(km.get_pool("openai").size, 2)

	def test_status_returns_all_providers(self):
		env = {
			"OPENAI_API_KEY": "sk-oai",
			"GROQ_API_KEY": "sk-groq",
		}
		km = KeyManager(getenv_fn=self._env(env))
		status = km.status()
		self.assertIn("openai", status)
		self.assertIn("groq", status)
		self.assertEqual(len(status["openai"]), 1)
		self.assertEqual(len(status["groq"]), 1)

	def test_singleton_identity(self):
		a = KeyManager(getenv_fn=self._env({"OPENAI_API_KEY": "sk-a"}))
		b = KeyManager(getenv_fn=self._env({"OPENAI_API_KEY": "sk-b"}))
		self.assertIs(a, b)

	def test_full_rotation_exhaustion_recovery(self):
		env = {
			"OPENAI_API_KEY_1": "sk-1",
			"OPENAI_API_KEY_2": "sk-2",
			"OPENAI_API_KEY_3": "sk-3",
		}
		km = KeyManager(getenv_fn=self._env(env))
		for i in range(3):
			km.record_failure("openai", i, is_rate_limit=True, rate_limit_seconds=120.0)
		self.assertIsNone(km.acquire_key("openai"))
		# Expire key-1 only
		pool = km.get_pool("openai")
		pool.keys()[1].rate_limited_until = time.time() - 1.0
		recovered = km.acquire_key("openai")
		self.assertIsNotNone(recovered)
		self.assertEqual(recovered.index, 1)


class TestErrorClassifierAndMetrics(unittest.TestCase):
	def test_classify_auth_quota_fatal_transient(self):
		self.assertEqual(ErrorClassifier.classify("401 unauthorized"), ErrorType.AUTH)
		self.assertEqual(ErrorClassifier.classify("insufficient_quota credits"), ErrorType.QUOTA)
		self.assertEqual(ErrorClassifier.classify("model_not_found"), ErrorType.FATAL)
		self.assertEqual(ErrorClassifier.classify("429 rate limit"), ErrorType.TRANSIENT)
		self.assertEqual(ErrorClassifier.classify("weird unknown blip"), ErrorType.TRANSIENT)

	def test_mask_short_and_long(self):
		self.assertEqual(KeyState(value="short", index=0).mask(), "***")
		masked = KeyState(value="sk-abcdefghij", index=0).mask()
		self.assertTrue(masked.startswith("sk-"))
		self.assertIn("...", masked)

	def test_metrics_summary(self):
		import os
		import tempfile

		with tempfile.TemporaryDirectory() as td:
			path = os.path.join(td, "m.jsonl")
			ml = MetricsLogger(path)
			ml.log(provider="openai", key_index=0, latency_ms=12.5, success=True)
			ml.log(
				provider="openai",
				key_index=0,
				latency_ms=30.0,
				success=False,
				error_type="TRANSIENT",
			)
			summary = ml.summary()
			self.assertEqual(summary["total"], 2)
			self.assertIn("openai", summary["providers"])
			prov = summary["providers"]["openai"]
			self.assertEqual(prov["requests"], 2)
			self.assertEqual(prov["rate_limit_events"], 1)
			# empty / missing file
			empty = MetricsLogger(os.path.join(td, "missing.jsonl"))
			self.assertEqual(empty.summary()["total"], 0)

	def test_provider_from_api_key_name(self):
		self.assertEqual(provider_from_api_key_name("OPENAI_API_KEY"), "openai")
		self.assertEqual(provider_from_api_key_name("CUSTOM_API_KEY"), "custom")

	def test_half_open_is_circuit_open_false(self):
		ks = KeyState(value="sk-test", index=0, circuit_threshold=1, circuit_cooldown=0.01)
		ks.record_failure()
		time.sleep(0.02)
		self.assertFalse(ks.is_circuit_open())
		# Already HALF_OPEN: second call still False
		self.assertFalse(ks.is_circuit_open())
		self.assertEqual(ks.circuit_state, CircuitState.HALF_OPEN)


if __name__ == "__main__":
	unittest.main()
