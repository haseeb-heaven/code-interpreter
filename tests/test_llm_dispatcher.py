"""Unit tests for llm_dispatcher routing and error handling (#224)."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libs.llm_dispatcher import (
	_detect_provider,
	build_completion_kwargs,
	dispatch_completion,
)


class TestModelRouting(unittest.TestCase):
	def test_detect_openai(self):
		self.assertEqual(_detect_provider("gpt-4o", "", "None"), "openai")
		self.assertEqual(_detect_provider("o3-mini", "", "None"), "openai")

	def test_detect_gemini(self):
		self.assertEqual(_detect_provider("gemini/gemini-2.5-flash", "", "None"), "gemini")

	def test_detect_groq(self):
		self.assertEqual(_detect_provider("groq/llama-3.1", "", "None"), "groq")

	def test_detect_local_from_provider(self):
		self.assertEqual(
			_detect_provider("llama3", "ollama", "http://localhost:11434/v1"),
			"local",
		)

	def test_detect_openrouter(self):
		self.assertEqual(
			_detect_provider("openrouter/free", "openrouter", "https://openrouter.ai/api/v1"),
			"openrouter",
		)

	def test_build_kwargs_openai(self):
		kwargs = build_completion_kwargs(
			model="gpt-4o",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.1,
			max_tokens=128,
			config_provider="",
			api_base="None",
		)
		self.assertEqual(kwargs["messages"][0]["content"], "hi")
		self.assertEqual(kwargs["max_tokens"], 128)

	def test_build_kwargs_local_requires_api_base(self):
		with self.assertRaises(ValueError):
			build_completion_kwargs(
				model="local-model",
				messages=[{"role": "user", "content": "hi"}],
				temperature=0.1,
				max_tokens=64,
				config_provider="local",
				api_base="None",
			)

	def test_build_kwargs_local_ok(self):
		kwargs = build_completion_kwargs(
			model="local-model",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.1,
			max_tokens=64,
			config_provider="ollama",
			api_base="http://127.0.0.1:11434/v1",
		)
		self.assertEqual(kwargs["api_base"], "http://127.0.0.1:11434/v1")
		self.assertEqual(kwargs["custom_llm_provider"], "openai")

	def test_build_kwargs_openrouter_requires_key(self):
		env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
		with patch.dict(os.environ, env, clear=True):
			with self.assertRaises(ValueError) as ctx:
				build_completion_kwargs(
					model="openrouter/x",
					messages=[{"role": "user", "content": "hi"}],
					temperature=0.1,
					max_tokens=64,
					config_provider="openrouter",
					api_base="https://openrouter.ai/api/v1",
				)
			self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))

	def test_build_kwargs_stream_and_tools(self):
		kwargs = build_completion_kwargs(
			model="gpt-4o",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.1,
			max_tokens=64,
			config_provider="",
			api_base="None",
			stream=True,
			tools=[{"type": "function", "function": {"name": "read_file"}}],
		)
		self.assertTrue(kwargs["stream"])
		self.assertEqual(kwargs["tool_choice"], "auto")


class TestDispatchCompletion(unittest.TestCase):
	def test_routes_to_completion_fn(self):
		mock_fn = MagicMock(
			return_value=SimpleNamespace(
				choices=[SimpleNamespace(message=SimpleNamespace(content="result"))]
			)
		)
		text = dispatch_completion(
			model="gpt-4o",
			messages=[{"role": "user", "content": "hello"}],
			completion_fn=mock_fn,
			stream=False,
		)
		self.assertEqual(text, "result")
		self.assertTrue(mock_fn.called)
		call_kwargs = mock_fn.call_args.kwargs
		self.assertIn("messages", call_kwargs)

	def test_handles_api_error_gracefully(self):
		mock_fn = MagicMock(side_effect=Exception("API quota exceeded"))
		with self.assertRaises(Exception) as ctx:
			dispatch_completion(
				model="gpt-4o",
				messages=[{"role": "user", "content": "hello"}],
				completion_fn=mock_fn,
				stream=False,
			)
		self.assertIn("quota", str(ctx.exception).lower())


if __name__ == "__main__":
	unittest.main()
