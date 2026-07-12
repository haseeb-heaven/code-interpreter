"""Unit tests for free OpenRouter / catalog fallback on agentic LLM calls."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from libs.agent.llm import call_llm
from libs.free_llms import (
	FreeLLMCatalog,
	FreeModelsExhaustedError,
	format_free_models_exhausted_message,
	free_fallback_candidates,
	is_free_routing_failure,
)


STEALTH_502 = (
	'litellm.APIError: OpenrouterException - '
	'{"error":{"message":"Invalid URL: ","code":502,'
	'"metadata":{"provider_name":"Stealth"}}}'
)


class FreeRoutingFailureDetectionTests(unittest.TestCase):
	def test_detects_stealth_502(self):
		self.assertTrue(is_free_routing_failure(RuntimeError(STEALTH_502)))

	def test_detects_invalid_url(self):
		self.assertTrue(is_free_routing_failure(Exception('Invalid URL: ')))

	def test_ignores_auth_errors(self):
		self.assertFalse(is_free_routing_failure(Exception("Invalid API key")))
		self.assertFalse(is_free_routing_failure(Exception("401 unauthorized")))

	def test_exhausted_message_suggests_commands(self):
		msg = format_free_models_exhausted_message(
			["openrouter-free (openrouter/free)"],
			RuntimeError(STEALTH_502),
		)
		self.assertIn("/free", msg)
		self.assertIn("/model", msg)


class FreeFallbackCandidateTests(unittest.TestCase):
	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmpdir.cleanup)
		self.configs_dir = os.path.join(self._tmpdir.name, "configs")
		os.makedirs(self.configs_dir)
		specs = {
			"openrouter-free": {
				"provider": "openrouter",
				"api_base": "https://openrouter.ai/api/v1",
				"model": "openrouter/free",
			},
			"openrouter-qwen-free": {
				"provider": "openrouter",
				"api_base": "https://openrouter.ai/api/v1",
				"model": "qwen/qwen3-coder-480b:free",
			},
			"groq-llama": {
				"provider": "groq",
				"model": "groq/llama-3.1-8b-instant",
			},
		}
		for name, payload in specs.items():
			with open(os.path.join(self.configs_dir, f"{name}.json"), "w", encoding="utf-8") as handle:
				json.dump(payload, handle)

		catalog_dir = os.path.join(self.configs_dir, "free")
		os.makedirs(catalog_dir)
		self.catalog_path = os.path.join(catalog_dir, "catalog.json")
		with open(self.catalog_path, "w", encoding="utf-8") as handle:
			json.dump(
				{
					"models": [
						{
							"id": "openrouter-free",
							"config": "openrouter-free",
							"provider": "openrouter",
							"env_key": "OPENROUTER_API_KEY",
							"tier": "free",
						},
						{
							"id": "openrouter-qwen-free",
							"config": "openrouter-qwen-free",
							"provider": "openrouter",
							"env_key": "OPENROUTER_API_KEY",
							"tier": "free",
						},
						{
							"id": "groq-llama",
							"config": "groq-llama",
							"provider": "groq",
							"env_key": "GROQ_API_KEY",
							"tier": "free_tier",
						},
					]
				},
				handle,
			)
		self.catalog = FreeLLMCatalog.load(self.catalog_path)
		self.env = {"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"}

	def test_openrouter_fallback_prefers_other_openrouter(self):
		cands = free_fallback_candidates(
			"openrouter/free",
			catalog=self.catalog,
			environ=self.env,
			configs_dir=self.configs_dir,
		)
		self.assertTrue(cands)
		self.assertEqual(cands[0]["config"], "openrouter-qwen-free")
		self.assertEqual(cands[0]["model"], "qwen/qwen3-coder-480b:free")
		# Current openrouter-free must not appear
		self.assertNotIn("openrouter-free", [c["config"] for c in cands])


class CallLlmFreeFallbackTests(unittest.TestCase):
	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmpdir.cleanup)
		self.configs_dir = os.path.join(self._tmpdir.name, "configs")
		os.makedirs(self.configs_dir)
		for name, model in (
			("openrouter-free", "openrouter/free"),
			("openrouter-qwen-free", "qwen/qwen3-coder-480b:free"),
		):
			with open(os.path.join(self.configs_dir, f"{name}.json"), "w", encoding="utf-8") as handle:
				json.dump(
					{
						"provider": "openrouter",
						"api_base": "https://openrouter.ai/api/v1",
						"model": model,
						"temperature": 0.1,
						"max_tokens": 256,
					},
					handle,
				)
		catalog_dir = os.path.join(self.configs_dir, "free")
		os.makedirs(catalog_dir)
		self.catalog_path = os.path.join(catalog_dir, "catalog.json")
		with open(self.catalog_path, "w", encoding="utf-8") as handle:
			json.dump(
				{
					"models": [
						{
							"id": "openrouter-free",
							"config": "openrouter-free",
							"provider": "openrouter",
							"env_key": "OPENROUTER_API_KEY",
							"tier": "free",
						},
						{
							"id": "openrouter-qwen-free",
							"config": "openrouter-qwen-free",
							"provider": "openrouter",
							"env_key": "OPENROUTER_API_KEY",
							"tier": "free",
						},
					]
				},
				handle,
			)

	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_falls_back_after_stealth_502(self, completion_mock, _cost):
		catalog = FreeLLMCatalog.load(self.catalog_path)

		ok = SimpleNamespace(
			choices=[SimpleNamespace(message=SimpleNamespace(content="Thought: ok\nAction: finish\nAction Input: {}"))],
			usage=SimpleNamespace(total_tokens=9),
		)

		def side_effect(**kwargs):
			model = kwargs.get("model")
			if model == "openrouter/free":
				raise RuntimeError(STEALTH_502)
			if model in ("qwen/qwen3-coder-480b:free", "openrouter/qwen/qwen3-coder-480b:free"):
				return ok
			raise AssertionError(f"unexpected model {model}")

		completion_mock.side_effect = side_effect
		fallback_hits = []

		with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"}, clear=False):
			content, metrics = call_llm(
				"openrouter/free",
				[{"role": "user", "content": "hi"}],
				configs_dir=self.configs_dir,
				catalog=catalog,
				on_fallback=fallback_hits.append,
			)

		self.assertIn("Thought:", content)
		self.assertEqual(metrics["model_used"], "qwen/qwen3-coder-480b:free")
		self.assertEqual(metrics["fallback_used"], 1.0)
		self.assertEqual(completion_mock.call_count, 2)
		self.assertEqual(len(fallback_hits), 1)
		self.assertEqual(fallback_hits[0]["model"], "qwen/qwen3-coder-480b:free")

	@patch("libs.agent.llm.litellm.completion")
	def test_exhausted_raises_friendly_error(self, completion_mock):
		catalog = FreeLLMCatalog.load(self.catalog_path)
		completion_mock.side_effect = RuntimeError(STEALTH_502)

		with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"}, clear=False):
			with self.assertRaises(FreeModelsExhaustedError) as ctx:
				call_llm(
					"openrouter/free",
					[{"role": "user", "content": "hi"}],
					configs_dir=self.configs_dir,
					catalog=catalog,
				)

		self.assertIn("/free", str(ctx.exception))
		self.assertIn("/model", str(ctx.exception))
		self.assertGreaterEqual(completion_mock.call_count, 2)

	@patch("libs.agent.llm.litellm.completion", side_effect=RuntimeError("down"))
	def test_non_routing_error_does_not_fallback(self, completion_mock):
		with self.assertRaises(RuntimeError):
			call_llm(
				"gpt-4o",
				[{"role": "user", "content": "hi"}],
				enable_free_fallback=False,
			)
		self.assertEqual(completion_mock.call_count, 1)


class ReActControllerFallbackUxTests(unittest.TestCase):
	@patch("libs.agent.react_controller.call_llm")
	def test_friendly_failure_without_traceback_dump(self, mock_llm):
		from libs.agent.react_controller import ReActController
		from libs.free_llms import FreeModelsExhaustedError

		mock_llm.side_effect = FreeModelsExhaustedError(
			"All free / cheap models failed after trying: openrouter/free. "
			"Use /free to list presets or /model <name> to switch models.",
			tried=["openrouter/free"],
		)
		controller = ReActController(model_name="openrouter/free", max_steps=2)
		# Avoid needing real sandbox for this failure-at-think path
		state = controller.run("say hi")
		self.assertEqual(state["status"], "FAILED")
		self.assertIn("/free", state["failure_reason"])
		self.assertIn("/model", state["failure_reason"])


if __name__ == "__main__":
	unittest.main()
