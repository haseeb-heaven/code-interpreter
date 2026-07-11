"""Unit tests for CodeExecutor and llm_dispatcher helpers."""

from __future__ import annotations

import asyncio
import io
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libs.execution.executor import CodeExecutor
from libs.llm_dispatcher import (
	_detect_provider,
	_has_openai_compatible_api_base,
	build_completion_kwargs,
	dispatch_completion,
)


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

	def test_execute_code_safe_mode_blocks_dangerous(self):
		interp = MagicMock()
		interp.UNSAFE_EXECUTION = False
		interp.logger = MagicMock()
		interp.safety_manager.is_dangerous_operation.return_value = True
		decision = MagicMock(allowed=False, reasons=["rm"])
		interp.safety_manager.assess_execution.return_value = decision
		out, err = CodeExecutor(interp).execute_code("os.remove('x')", "python")
		self.assertIsNone(out)
		self.assertIn("Safety blocked", err)

	def test_execute_code_user_declines(self):
		interp = MagicMock()
		interp.UNSAFE_EXECUTION = True
		interp.logger = MagicMock()
		interp.safety_manager.is_dangerous_operation.return_value = False
		interp._safe_input.return_value = "n"
		out, err = CodeExecutor(interp).execute_code("print(1)", "python")
		self.assertIsNone(out)
		self.assertIsNone(err)
		self.assertFalse(interp._last_execution_approved)

	def test_execute_code_force_execute_success(self):
		interp = MagicMock()
		interp.UNSAFE_EXECUTION = True
		interp.logger = MagicMock()
		interp.code_interpreter.execute_code.return_value = ("1\n", "")
		out, err = CodeExecutor(interp).execute_code("print(1)", "python", force_execute=True)
		self.assertEqual(out, "1\n")
		self.assertEqual(err, "")

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

	def test_execute_last_code_success_path(self):
		interp = MagicMock()
		interp.INTERPRETER_MODE = "code"
		interp.INTERPRETER_LANGUAGE = "python"
		interp.utility_manager.get_output_history.return_value = ("out.py", "print(1)")
		interp._execute_generated_output.return_value = ("1", None, None)
		interp.logger = MagicMock()
		shown = []
		CodeExecutor(interp).execute_last_code(
			"Windows",
			display_code_fn=lambda *a, **k: shown.append(a[0] if a else ""),
			display_markdown_fn=shown.append,
		)
		self.assertIn("print(1)", shown)
		self.assertIn("1", shown)

	def test_execute_async_python(self):
		interp = MagicMock()
		interp.UNSAFE_EXECUTION = True
		interp.logger = MagicMock()
		ex = CodeExecutor(interp)
		out, err = asyncio.run(ex.execute_async("print('async-ok')", "python", timeout=30))
		self.assertIn("async-ok", out or "")
		self.assertFalse(err)

	def test_execute_async_empty_and_unsupported(self):
		interp = MagicMock()
		interp.UNSAFE_EXECUTION = True
		interp.logger = MagicMock()
		ex = CodeExecutor(interp)
		out, err = asyncio.run(ex.execute_async("  ", "python"))
		self.assertIsNone(out)
		self.assertIn("empty", err.lower())
		out2, err2 = asyncio.run(ex.execute_async("echo hi", "ruby"))
		self.assertIsNone(out2)
		self.assertIn("Unsupported", err2)


class TestLlmDispatcher(unittest.TestCase):
	def test_has_openai_compatible_api_base(self):
		self.assertFalse(_has_openai_compatible_api_base("None"))
		self.assertFalse(_has_openai_compatible_api_base(""))
		self.assertTrue(_has_openai_compatible_api_base("http://localhost:11434/v1"))
		self.assertTrue(_has_openai_compatible_api_base("https://api.example/v1"))

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

	def test_build_completion_kwargs_local_requires_api_base(self):
		with self.assertRaises(ValueError):
			build_completion_kwargs(
				model="local-model",
				messages=[],
				temperature=0.1,
				max_tokens=16,
				config_provider="local",
				api_base="None",
			)

	@patch.dict("os.environ", {"OPENROUTER_API_KEY": "or-key"}, clear=False)
	def test_build_completion_kwargs_openrouter(self):
		kwargs = build_completion_kwargs(
			model="openrouter/free",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.1,
			max_tokens=16,
			config_provider="openrouter",
			api_base="https://openrouter.ai/api/v1",
			tools=[{"type": "function", "function": {"name": "x"}}],
		)
		self.assertEqual(kwargs["api_key"], "or-key")
		self.assertEqual(kwargs["custom_llm_provider"], "openai")
		self.assertIn("extra_headers", kwargs)
		self.assertEqual(kwargs["tool_choice"], "auto")

	def test_build_completion_kwargs_reasoning_model_drops_temperature(self):
		kwargs = build_completion_kwargs(
			model="o3-mini",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.5,
			max_tokens=16,
			config_provider="",
			api_base="None",
		)
		self.assertNotIn("temperature", kwargs)
		self.assertTrue(kwargs.get("drop_params"))

	def test_dispatch_completion_non_stream(self):
		response = SimpleNamespace(
			choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))]
		)
		text = dispatch_completion(
			model="gpt-4o",
			messages=[{"role": "user", "content": "hi"}],
			completion_fn=lambda model, **kw: response,
			stream=False,
		)
		self.assertEqual(text, "hello")

	def test_dispatch_completion_stream_fallback_to_object(self):
		response = {
			"choices": [{"message": {"content": "streamed"}}],
		}
		buf = io.StringIO()
		with patch("builtins.print") as _print:
			text = dispatch_completion(
				model="gpt-4o",
				messages=[{"role": "user", "content": "hi"}],
				completion_fn=lambda model, **kw: response,
				stream=True,
				show_stream=True,
			)
		self.assertEqual(text, "streamed")


if __name__ == "__main__":
	unittest.main()
