"""Unit tests for libs.core.model_router.ModelRouter."""

from __future__ import annotations

import os
import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from libs.core.model_router import ModelRouter
from libs.interpreter_lib import Interpreter


class TestModelRouter(unittest.TestCase):
	def _make_interp(self, mode="code", model="gpt-4o"):
		from tests.helpers.cli_args import make_interpreter_args

		with patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None), \
			 patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None):
			args = make_interpreter_args(mode=mode, model=model)
			return Interpreter(args)

	def test_is_recoverable_runtime_error_rate_limit(self):
		self.assertTrue(ModelRouter.is_recoverable_runtime_error("Rate limit exceeded"))
		self.assertTrue(ModelRouter.is_recoverable_runtime_error("HTTP 429 Too Many Requests"))
		self.assertFalse(ModelRouter.is_recoverable_runtime_error("syntax error near unexpected token"))

	def test_is_recoverable_runtime_error_uses_shared_billing_auth_markers(self):
		from libs.core.error_classification import BILLING_AUTH_MARKERS

		for marker in BILLING_AUTH_MARKERS:
			self.assertTrue(
				ModelRouter.is_recoverable_runtime_error(f"boom: {marker} happened"),
				f"expected marker {marker!r} to be recoverable",
			)

	def test_is_retryable_excludes_billing(self):
		self.assertFalse(ModelRouter.is_retryable_request_error("requires more credits"))
		self.assertTrue(ModelRouter.is_retryable_request_error("timeout talking to provider"))

	def test_format_runtime_error_strips_urls_and_prefixes(self):
		raw = "litellm.RateLimitError: https://example.com/docs oops RateLimitError: slow down"
		cleaned = ModelRouter.format_runtime_error_message(raw)
		self.assertNotIn("https://", cleaned)
		self.assertNotIn("litellm.", cleaned)

	def test_extract_latest_user_text_from_string(self):
		self.assertEqual(ModelRouter.extract_latest_user_text("hello there", []), "hello there")

	def test_extract_latest_user_text_from_messages(self):
		messages = [
			{"role": "system", "content": "sys"},
			{"role": "user", "content": "first"},
			{"role": "user", "content": "latest question"},
		]
		self.assertEqual(ModelRouter.extract_latest_user_text("", messages), "latest question")

	def test_generate_content_calls_completion_fn(self):
		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.config_values = {"temperature": 0.1, "max_tokens": 64, "api_base": "None"}
		fake_response = MagicMock()
		completion_fn = MagicMock(return_value=fake_response)
		with patch.object(interp.utility_manager, "_extract_content", return_value="print(1)"):
			text = interp.model_router.generate_content(
				"print 1", [],
				config_values=interp.config_values,
				completion_fn=completion_fn,
				getenv_fn=lambda *_: "sk-test",
			)
		self.assertEqual(text, "print(1)")
		self.assertTrue(completion_fn.called)

	def test_initialize_client_sets_default_key_for_local_model(self):
		interp = self._make_interp(model="local-model")
		interp.INTERPRETER_MODEL = "local-llama"
		interp.config_values = {"model": "local-llama", "provider": "local", "api_base": "http://localhost:11434/v1"}
		environ = {}
		with patch.object(interp.utility_manager, "read_config_file", return_value=interp.config_values):
			interp.model_router.initialize_client(
				load_dotenv_fn=lambda **_: None,
				getenv_fn=lambda *_: None,
				environ=environ,
			)
		self.assertEqual(environ.get("OPENAI_API_KEY"), "sk-1234567890")

	def test_generate_content_with_retries_free_fallback_success(self):
		from libs.key_manager import AllKeysExhaustedError

		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 1
		interp.config_values = {}
		interp.args.free = True
		km = MagicMock()
		km.acquire_key.return_value = None
		km.has_pool.return_value = True
		km.raise_if_exhausted.side_effect = AllKeysExhaustedError(
			"All keys exhausted for provider 'openai'. Earliest recovery: 2026-07-13T12:00:00Z",
			provider="openai",
			earliest_recovery_ts=1815000000.0,
		)
		interp._key_manager = km

		with patch("libs.agent.llm.complete_with_free_fallback") as fallback, \
		     patch.object(interp.utility_manager, "_extract_content", return_value="fallback text"):
			fake_response = MagicMock()
			fallback.return_value = (fake_response, {"provider": "groq"})
			result = interp.model_router.generate_content_with_retries(
				"hello", [], config_values={},
				sleep_fn=lambda *_: None, display_fn=lambda *_: None,
			)

		self.assertEqual(result, "fallback text")
		fallback.assert_called_once()

	def test_generate_content_with_retries_free_fallback_disabled_raises(self):
		from libs.key_manager import AllKeysExhaustedError

		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 1
		interp.config_values = {}
		interp.args.free = False
		km = MagicMock()
		km.acquire_key.return_value = None
		km.has_pool.return_value = True
		km.raise_if_exhausted.side_effect = AllKeysExhaustedError(
			"All keys exhausted for provider 'openai'. Earliest recovery: 2026-07-13T12:00:00Z",
			provider="openai",
			earliest_recovery_ts=1815000000.0,
		)
		interp._key_manager = km

		with patch("libs.agent.llm.complete_with_free_fallback") as fallback:
			with self.assertRaises(AllKeysExhaustedError):
				interp.model_router.generate_content_with_retries(
					"hello", [], config_values={},
					sleep_fn=lambda *_: None, display_fn=lambda *_: None,
				)
		fallback.assert_not_called()

	def test_generate_content_with_retries_free_fallback_itself_fails_raises_original(self):
		from libs.key_manager import AllKeysExhaustedError

		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 1
		interp.config_values = {}
		interp.args.free = True
		km = MagicMock()
		km.acquire_key.return_value = None
		km.has_pool.return_value = True
		km.raise_if_exhausted.side_effect = AllKeysExhaustedError(
			"All keys exhausted for provider 'openai'. Earliest recovery: 2026-07-13T12:00:00Z",
			provider="openai",
			earliest_recovery_ts=1815000000.0,
		)
		interp._key_manager = km

		with patch("libs.agent.llm.complete_with_free_fallback", side_effect=RuntimeError("no free provider configured")):
			with self.assertRaises(AllKeysExhaustedError):
				interp.model_router.generate_content_with_retries(
					"hello", [], config_values={},
					sleep_fn=lambda *_: None, display_fn=lambda *_: None,
				)

	def test_generate_content_with_retries_async_free_fallback_success(self):
		import asyncio
		from libs.key_manager import AllKeysExhaustedError

		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 1
		interp.config_values = {}
		interp.args.free = True
		km = MagicMock()
		km.acquire_key.return_value = None
		km.has_pool.return_value = True
		km.raise_if_exhausted.side_effect = AllKeysExhaustedError(
			"All keys exhausted for provider 'openai'. Earliest recovery: 2026-07-13T12:00:00Z",
			provider="openai",
			earliest_recovery_ts=1815000000.0,
		)
		interp._key_manager = km

		with patch("libs.agent.llm.complete_with_free_fallback") as fallback, \
		     patch.object(interp.utility_manager, "_extract_content", return_value="async fallback text"):
			fake_response = MagicMock()
			fallback.return_value = (fake_response, {"provider": "groq"})
			result = asyncio.run(
				interp.model_router.generate_content_with_retries_async(
					"hello", [], config_values={},
					sleep_fn=lambda *_: None, display_fn=lambda *_: None,
				)
			)

		self.assertEqual(result, "async fallback text")
		fallback.assert_called_once()


class TestModelRouterKeyRotation(unittest.TestCase):
	def setUp(self):
		from libs.key_manager import KeyManager
		KeyManager.reset_singleton()

	def tearDown(self):
		from libs.key_manager import KeyManager
		KeyManager.reset_singleton()
		for key in ("OPENAI_API_KEY", "OPENAI_API_KEY_1", "OPENAI_API_KEY_2"):
			os.environ.pop(key, None)

	def _make_interp(self, mode="code", model="gpt-4o"):
		from tests.helpers.cli_args import make_interpreter_args
		with patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None), \
		     patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None):
			args = make_interpreter_args(mode=mode, model=model)
			return Interpreter(args)

	def _env(self, mapping):
		def getenv(name, default=None):
			return mapping.get(name, default)
		return getenv

	def test_generate_content_with_retries_rotates_to_second_key_on_failure(self):
		from libs.key_manager import KeyManager

		env = {"OPENAI_API_KEY_1": "sk-1", "OPENAI_API_KEY_2": "sk-2"}
		km = KeyManager(getenv_fn=self._env(env))
		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 3
		interp.config_values = {}
		interp._key_manager = km
		interp.args.free = False

		seen_keys = []
		call_count = {"n": 0}

		def fake_generate_content(message, chat_history, config_values=None, image_file=None):
			call_count["n"] += 1
			seen_keys.append(os.environ.get("OPENAI_API_KEY"))
			if call_count["n"] == 1:
				raise RuntimeError("429 rate limit exceeded")
			return "ok from second key"

		interp.generate_content = fake_generate_content

		result = interp.model_router.generate_content_with_retries(
			"hello", [], config_values={},
			sleep_fn=lambda *_: None, display_fn=lambda *_: None,
		)

		self.assertEqual(result, "ok from second key")
		self.assertEqual(call_count["n"], 2)
		self.assertEqual(seen_keys[0], "sk-1")
		self.assertEqual(seen_keys[1], "sk-2")


if __name__ == "__main__":
	unittest.main()
