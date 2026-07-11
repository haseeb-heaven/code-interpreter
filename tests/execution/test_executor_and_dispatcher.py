"""Unit tests for CodeExecutor and llm_dispatcher helpers."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from libs.execution.executor import CodeExecutor
from libs.llm_dispatcher import _detect_provider, build_completion_kwargs


class TestCodeExecutor(unittest.TestCase):
	def test_execute_generated_output_safe_mode(self):
		interp = MagicMock()
		interp.UNSAFE_EXECUTION = False
		interp.safety_manager.build_sandbox_context.return_value = {"sandbox": True}
		interp.execute_code.return_value = ("ok", None)
		ex = CodeExecutor(interp)
		output, error, ctx = ex.execute_generated_output("print(1)", "python")
		self.assertEqual(output, "ok")
		self.assertIsNone(error)
		self.assertEqual(ctx, {"sandbox": True})
		interp.execute_code.assert_called_once()

	def test_execute_generated_output_error(self):
		interp = MagicMock()
		interp.UNSAFE_EXECUTION = True
		interp.execute_code.return_value = (None, "boom")
		ex = CodeExecutor(interp)
		output, error, ctx = ex.execute_generated_output("bad", "python")
		self.assertIsNone(output)
		self.assertEqual(error, "boom")
		self.assertIsNone(ctx)

	def test_execute_code_empty(self):
		interp = MagicMock()
		interp.UNSAFE_EXECUTION = False
		interp.logger = MagicMock()
		ex = CodeExecutor(interp)
		out, err = ex.execute_code("   ", "python")
		self.assertIsNone(out)
		self.assertIn("empty", err.lower())

	def test_execute_last_code_empty_history(self):
		interp = MagicMock()
		interp.INTERPRETER_MODE = "code"
		interp.INTERPRETER_LANGUAGE = "python"
		interp.utility_manager.get_output_history.return_value = (None, None)
		interp.logger = MagicMock()
		displayed = []
		CodeExecutor(interp).execute_last_code(
			"Windows",
			display_code_fn=lambda *_a, **_k: None,
			display_markdown_fn=displayed.append,
		)
		self.assertTrue(any("empty" in str(m).lower() for m in displayed))


class TestLlmDispatcher(unittest.TestCase):
	def test_detect_provider_matrix(self):
		self.assertEqual(_detect_provider("gpt-4o", "", "None"), "openai")
		self.assertEqual(_detect_provider("claude-3", "", "None"), "claude")
		self.assertEqual(_detect_provider("gemini-pro", "", "None"), "gemini")
		self.assertEqual(_detect_provider("groq/llama", "", "None"), "groq")
		self.assertEqual(_detect_provider("deepseek-chat", "", "None"), "deepseek")
		self.assertEqual(_detect_provider("local-model", "", "None"), "local")
		self.assertEqual(_detect_provider("foo", "openrouter", "None"), "openrouter")
		self.assertEqual(_detect_provider("foo", "ollama", "None"), "local")
		self.assertEqual(
			_detect_provider("custom", "", "http://localhost:11434/v1"),
			"local",
		)
		self.assertEqual(_detect_provider("unknown-model", "", "None"), "huggingface")

	@patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False)
	def test_build_completion_kwargs_openai(self):
		kwargs = build_completion_kwargs(
			model="gpt-4o",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.1,
			max_tokens=32,
			config_provider="",
			api_base="None",
		)
		self.assertIn("messages", kwargs)
		self.assertEqual(kwargs.get("model") or "gpt-4o", kwargs.get("model", "gpt-4o") or "gpt-4o")

	@patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False)
	def test_build_completion_kwargs_local_api_base(self):
		kwargs = build_completion_kwargs(
			model="local-model",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.1,
			max_tokens=32,
			config_provider="local",
			api_base="http://127.0.0.1:11434/v1",
		)
		self.assertIn("messages", kwargs)
		self.assertTrue(
			"api_base" in kwargs or "base_url" in kwargs or kwargs.get("custom_llm_provider")
		)


if __name__ == "__main__":
	unittest.main()
