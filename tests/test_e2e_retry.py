"""Mocked E2E integration tests for key rotation / retry resilience (#213/#214).

AUTH behavior (shipped #213): Auth failures permanently break the failing key.
Retries continue only when another key in the pool is still available. With a
single key, AUTH surfaces immediately (no retry) — asserted below.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from argparse import Namespace
from unittest.mock import patch

from libs.core.model_router import ModelRouter
from libs.interpreter_lib import Interpreter
from libs.key_manager import AllKeysExhaustedError, KeyManager, MetricsLogger


def _fake_completion_ok(*_args, **_kwargs):
	return "print('ok')"


class TestE2ERetry(unittest.TestCase):
	def setUp(self):
		KeyManager.reset_singleton()
		self._tmpdir = tempfile.TemporaryDirectory()
		self._metrics_path = os.path.join(self._tmpdir.name, "metrics.jsonl")
		# Isolate os.environ mutations from other tests
		self._env_patcher = patch.dict(os.environ, {}, clear=False)
		self._env_patcher.start()

	def tearDown(self):
		self._env_patcher.stop()
		KeyManager.reset_singleton()
		self._tmpdir.cleanup()

	def _make_interp(self, *, keys, max_retries=5, model="gpt-4o"):
		"""Build Interpreter + KeyManager with numbered OPENAI keys (test-only)."""
		from tests.helpers.cli_args import make_interpreter_args

		with patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None), patch(
			"libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None
		):
			args = make_interpreter_args(model=model)
			interp = Interpreter(args)

		env = {}
		for i, key in enumerate(keys, start=1):
			env[f"OPENAI_API_KEY_{i}"] = key
		# Bare key must not shadow numbered discovery
		env.pop("OPENAI_API_KEY", None)

		def getenv(name, default=None):
			return env.get(name, default)

		KeyManager.reset_singleton()
		km = KeyManager(
			getenv_fn=getenv,
			config={
				"circuit_breaker": {"threshold": 3, "cooldown_seconds": 120},
				"rate_limits": {"rpm": 600, "burst": 50},
			},
		)
		km.metrics = MetricsLogger(self._metrics_path)
		interp._key_manager = km
		interp.INTERPRETER_MODEL = model
		interp.MAX_LLM_RETRIES = max_retries
		interp.config_values = {
			"provider": "openai",
			"temperature": 0.1,
			"max_tokens": 64,
			"api_base": "None",
		}
		return interp, km, env

	def _run_retries(self, interp, sleep_fn=None):
		sleeps = []

		def _sleep(seconds):
			sleeps.append(seconds)
			if sleep_fn is not None:
				sleep_fn(seconds)

		return (
			interp.model_router.generate_content_with_retries(
				"ping",
				[],
				config_values=interp.config_values,
				sleep_fn=_sleep,
				display_fn=lambda *_: None,
			),
			sleeps,
		)

	@patch("litellm.completion")
	def test_single_key_429_recovers_after_backoff(self, mock_completion):
		interp, km, _env = self._make_interp(keys=["sk-only"], max_retries=5)
		# First call rate-limits; after backoff key is still rate-limited for 60s
		# by default — expire it so the second attempt can reuse the same key.
		call_keys = []

		def side_effect(*args, **kwargs):
			call_keys.append(os.environ.get("OPENAI_API_KEY"))
			if len(call_keys) == 1:
				# Mark short rate-limit so we can expire between attempts
				raise Exception("Error code: 429 - Rate limit exceeded")
			return _fake_completion_ok()

		mock_completion.side_effect = side_effect

		def sleep_and_expire(_seconds):
			pool = km.get_pool("openai")
			pool.keys()[0].rate_limited_until = time.time() - 1.0

		result, sleeps = self._run_retries(interp, sleep_fn=sleep_and_expire)
		self.assertEqual(result, "print('ok')")
		self.assertEqual(mock_completion.call_count, 2)
		self.assertEqual(call_keys, ["sk-only", "sk-only"])
		self.assertTrue(sleeps)  # backoff invoked

	@patch("litellm.completion")
	def test_two_key_rotation_on_rate_limit(self, mock_completion):
		interp, km, _env = self._make_interp(keys=["sk-1", "sk-2"], max_retries=5)
		seen = []

		def side_effect(*args, **kwargs):
			key = os.environ.get("OPENAI_API_KEY")
			seen.append(key)
			if key == "sk-1":
				raise Exception("429 Rate limit exceeded")
			return _fake_completion_ok()

		mock_completion.side_effect = side_effect
		result, _ = self._run_retries(interp)
		self.assertEqual(result, "print('ok')")
		self.assertIn("sk-1", seen)
		self.assertEqual(seen[-1], "sk-2")
		# Key-1 rate-limited; key-2 recorded success
		pool = km.get_pool("openai")
		self.assertFalse(pool.keys()[0].is_available())
		self.assertEqual(pool.keys()[1].successes, 1)

	@patch("litellm.completion")
	def test_three_key_all_exhausted_raises(self, mock_completion):
		interp, _km, _env = self._make_interp(keys=["sk-1", "sk-2", "sk-3"], max_retries=3)
		mock_completion.side_effect = Exception("429 Rate limit exceeded")
		with self.assertRaises(AllKeysExhaustedError) as ctx:
			self._run_retries(interp)
		msg = str(ctx.exception)
		self.assertIn("All keys exhausted", msg)
		self.assertIn("Earliest recovery", msg)
		self.assertEqual(mock_completion.call_count, 3)

	@patch("litellm.completion")
	def test_transient_503_retries_with_backoff(self, mock_completion):
		interp, _km, _env = self._make_interp(keys=["sk-a"], max_retries=5)
		# Transient (non-429) failures increment circuit but do not rate-limit,
		# so the same key stays available across retries.
		mock_completion.side_effect = [
			Exception("503 Service Unavailable"),
			Exception("503 Service Unavailable"),
			_fake_completion_ok(),
		]
		with patch.object(ModelRouter, "_jitter_backoff_seconds", side_effect=[0.01, 0.02, 0.04]):
			started = time.monotonic()
			result, sleeps = self._run_retries(interp)
			elapsed = time.monotonic() - started
		self.assertEqual(result, "print('ok')")
		self.assertEqual(mock_completion.call_count, 3)
		self.assertEqual(sleeps, [0.01, 0.02])
		self.assertLess(elapsed, 2.0)

	@patch("litellm.completion")
	def test_auth_error_does_not_retry(self, mock_completion):
		"""Single-key AUTH: completion called once; no second litellm attempt.

		Deviation from issue wording ("401 surfaced"): shipped #213 permanently
		breaks the AUTH key then raises AllKeysExhaustedError when the pool has
		no remaining healthy keys (raise_if_exhausted before re-raising). With
		multiple keys, AUTH rotates to the next available key instead.
		"""
		interp, km, _env = self._make_interp(keys=["sk-bad"], max_retries=5)
		mock_completion.side_effect = Exception("401 Unauthorized: invalid api key")
		with self.assertRaises(AllKeysExhaustedError) as ctx:
			self._run_retries(interp)
		self.assertIn("All keys exhausted", str(ctx.exception))
		self.assertEqual(mock_completion.call_count, 1)
		self.assertTrue(km.get_pool("openai").keys()[0].permanently_broken)

	@patch("litellm.completion")
	def test_fatal_error_does_not_retry(self, mock_completion):
		interp, _km, _env = self._make_interp(keys=["sk-1", "sk-2"], max_retries=5)
		mock_completion.side_effect = Exception("model_not_found: does not exist")
		with self.assertRaises(Exception) as ctx:
			self._run_retries(interp)
		self.assertIn("model_not_found", str(ctx.exception))
		self.assertEqual(mock_completion.call_count, 1)

	@patch("litellm.completion")
	def test_quota_error_applies_long_backoff(self, mock_completion):
		interp, km, _env = self._make_interp(keys=["sk-q"], max_retries=3)
		mock_completion.side_effect = Exception("insufficient_quota: requires more credits")
		# Quota is retryable but key is dark for 600s → next acquire fails → exhaustion
		with self.assertRaises((AllKeysExhaustedError, Exception)):
			self._run_retries(interp)
		ks = km.get_pool("openai").keys()[0]
		# Quota uses 600s default, not the 60s rate-limit window
		self.assertGreaterEqual(ks.rate_limited_until, time.time() + 500)

	@patch("litellm.completion")
	def test_successful_call_records_success(self, mock_completion):
		interp, km, _env = self._make_interp(keys=["sk-ok"], max_retries=3)
		mock_completion.side_effect = _fake_completion_ok
		result, _ = self._run_retries(interp)
		self.assertEqual(result, "print('ok')")
		ks = km.get_pool("openai").keys()[0]
		self.assertEqual(ks.failures, 0)
		self.assertEqual(ks.successes, 1)

	@patch("litellm.completion")
	def test_metrics_jsonl_written_after_call(self, mock_completion):
		interp, km, _env = self._make_interp(keys=["sk-m"], max_retries=3)
		# Fresh metrics file
		if os.path.exists(self._metrics_path):
			os.remove(self._metrics_path)
		km.metrics = MetricsLogger(self._metrics_path)
		mock_completion.side_effect = _fake_completion_ok
		self._run_retries(interp)
		self.assertTrue(os.path.exists(self._metrics_path))
		with open(self._metrics_path, encoding="utf-8") as fh:
			lines = [ln.strip() for ln in fh if ln.strip()]
		self.assertEqual(len(lines), 1)
		row = json.loads(lines[0])
		self.assertEqual(row["provider"], "openai")
		self.assertEqual(row["key_index"], 0)
		self.assertTrue(row["success"])
		self.assertIn("latency_ms", row)
		self.assertIn("timestamp", row)


if __name__ == "__main__":
	unittest.main()
