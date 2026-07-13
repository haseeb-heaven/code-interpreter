"""Unit tests for libs.core.model_router.ModelRouter."""

from __future__ import annotations

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


if __name__ == "__main__":
	unittest.main()
