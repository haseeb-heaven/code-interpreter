"""Unit tests for free OpenRouter / catalog fallback on agentic LLM calls.

Covers CI-critical regressions (mocked, no live keys):
1. Dead/invalid OpenRouter free IDs skipped; catalog rotation continues
2. Stealth 502 / Invalid URL → next free preset
3. RateLimitError 429 + \"try again in Ns\" → sleep/retry then succeed OR next model
4. After fallback, subsequent call_llm uses updated model (no sticky dead model)
5. ReAct path: rate-limit does not dump unhandled; fallback or clean tip
6. /model with no args is a command (list), not a ReAct task
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libs.agent.llm import call_llm
from libs.free_llms import (
	FreeLLMCatalog,
	FreeModelsExhaustedError,
	format_free_models_exhausted_message,
	free_fallback_candidates,
	is_free_routing_failure,
	parse_retry_after_seconds,
)


STEALTH_502 = (
	'litellm.APIError: OpenrouterException - '
	'{"error":{"message":"Invalid URL: ","code":502,'
	'"metadata":{"provider_name":"Stealth"}}}'
)

GROQ_429 = (
	"litellm.RateLimitError: RateLimitError: GroqException - "
	'{"error":{"message":"Rate limit reached for model `llama-3.1-8b-instant` '
	"in organization org_test on tokens per minute (TPM): Limit 6000, Used 5990, "
	'Requested 50. Please try again in 2.5s. Visit https://console.groq.com/docs/rate-limits '
	'for more information.","type":"tokens","code":"rate_limit_exceeded"}}'
)

OPENROUTER_429 = (
	"litellm.RateLimitError: RateLimitError: OpenrouterException - "
	'{"error":{"message":"Rate limit exceeded: try again in 1.2s","code":429}}'
)


def _ok_response(text: str = "Thought: ok\nAction: finish\nAction Input: {}"):
	return SimpleNamespace(
		choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
		usage=SimpleNamespace(total_tokens=9),
	)


def _write_json(path: str, payload: dict) -> None:
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as handle:
		json.dump(payload, handle)


class FreeRoutingFailureDetectionTests(unittest.TestCase):
	def test_detects_stealth_502(self):
		self.assertTrue(is_free_routing_failure(RuntimeError(STEALTH_502)))

	def test_detects_invalid_url(self):
		self.assertTrue(is_free_routing_failure(Exception("Invalid URL: ")))

	def test_detects_rate_limit_429(self):
		self.assertTrue(is_free_routing_failure(RuntimeError(GROQ_429)))
		self.assertTrue(is_free_routing_failure(Exception(OPENROUTER_429)))
		self.assertTrue(is_free_routing_failure(Exception("Error code: 429 - rate_limit_exceeded")))

	def test_ignores_auth_errors(self):
		self.assertFalse(is_free_routing_failure(Exception("Invalid API key")))
		self.assertFalse(is_free_routing_failure(Exception("401 unauthorized")))

	def test_parse_retry_after_from_try_again_in(self):
		self.assertAlmostEqual(parse_retry_after_seconds(GROQ_429), 2.5, places=2)
		self.assertAlmostEqual(parse_retry_after_seconds(OPENROUTER_429), 1.2, places=2)
		self.assertIsNone(parse_retry_after_seconds("no retry hint"))

	def test_parse_retry_after_capped(self):
		raw = "Please try again in 120.0s."
		secs = parse_retry_after_seconds(raw, cap=35.0)
		self.assertEqual(secs, 35.0)

	def test_exhausted_message_suggests_commands(self):
		msg = format_free_models_exhausted_message(
			["openrouter-free (openrouter/free)"],
			RuntimeError(STEALTH_502),
		)
		self.assertIn("/free", msg)
		self.assertIn("/model", msg)
		# Never leak secrets in exhausted messaging
		self.assertNotIn("sk-", msg)
		self.assertNotIn("api_key", msg.lower())


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
				"model": "qwen/qwen3-coder:free",
			},
			"groq-llama": {
				"provider": "groq",
				"model": "groq/llama-3.1-8b-instant",
			},
		}
		for name, payload in specs.items():
			_write_json(os.path.join(self.configs_dir, f"{name}.json"), payload)

		catalog_dir = os.path.join(self.configs_dir, "free")
		self.catalog_path = os.path.join(catalog_dir, "catalog.json")
		_write_json(
			self.catalog_path,
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
		self.assertEqual(cands[0]["model"], "qwen/qwen3-coder:free")
		self.assertNotIn("openrouter-free", [c["config"] for c in cands])

	def test_dead_catalog_entries_without_config_file_are_skipped(self):
		"""Catalog rotation continues when a listed free ID has no config file."""
		# Inject a dead catalog entry pointing at a missing config file
		_write_json(
			self.catalog_path,
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
						"id": "openrouter-dead-qwen-480b",
						"config": "openrouter-qwen3-coder-480b-free",
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
		)
		catalog = FreeLLMCatalog.load(self.catalog_path)
		available = catalog.available(environ=self.env, configs_dir=self.configs_dir)
		configs = [e.config for e in available]
		self.assertIn("openrouter-free", configs)
		self.assertIn("groq-llama", configs)
		self.assertNotIn("openrouter-qwen3-coder-480b-free", configs)

		cands = free_fallback_candidates(
			"openrouter/free",
			catalog=catalog,
			environ=self.env,
			configs_dir=self.configs_dir,
		)
		self.assertTrue(cands)
		self.assertEqual(cands[0]["config"], "groq-llama")
		self.assertNotIn("openrouter-qwen3-coder-480b-free", [c["config"] for c in cands])


class RepoCatalogHygieneTests(unittest.TestCase):
	"""Live catalog must not advertise known-dead OpenRouter free IDs."""

	DEAD_MODEL_SNIPPETS = (
		"qwen3-coder-480b:free",
		"mimo-v2-flash:free",
		"nemotron-3-super:free",
		"minimax-m2.5:free",
		"qwen3.6-plus:free",
	)

	def test_repo_free_catalog_omits_dead_openrouter_ids(self):
		catalog_path = os.path.join("configs", "free", "catalog.json")
		self.assertTrue(os.path.isfile(catalog_path), "configs/free/catalog.json missing")
		with open(catalog_path, "r", encoding="utf-8") as handle:
			payload = json.load(handle)
		blob = json.dumps(payload).lower()
		for dead in self.DEAD_MODEL_SNIPPETS:
			self.assertNotIn(dead.lower(), blob, f"dead free id still in catalog: {dead}")

		# Prefer currently valid free presets still present
		ids = [m.get("id") or m.get("config") for m in payload.get("models", [])]
		self.assertIn("openrouter-free", ids)
		self.assertTrue(
			any("groq" in str(i) for i in ids),
			"catalog should keep at least one Groq free-tier preset",
		)


class CallLlmFreeFallbackTests(unittest.TestCase):
	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmpdir.cleanup)
		self.configs_dir = os.path.join(self._tmpdir.name, "configs")
		os.makedirs(self.configs_dir)
		for name, model in (
			("openrouter-free", "openrouter/free"),
			("openrouter-qwen-free", "qwen/qwen3-coder:free"),
			("groq-llama", "groq/llama-3.1-8b-instant"),
		):
			provider = "groq" if name.startswith("groq") else "openrouter"
			payload = {
				"provider": provider,
				"model": model,
				"temperature": 0.1,
				"max_tokens": 256,
			}
			if provider == "openrouter":
				payload["api_base"] = "https://openrouter.ai/api/v1"
			_write_json(os.path.join(self.configs_dir, f"{name}.json"), payload)

		self.catalog_path = os.path.join(self.configs_dir, "free", "catalog.json")
		_write_json(
			self.catalog_path,
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
		)

	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_falls_back_after_stealth_502(self, completion_mock, _cost):
		catalog = FreeLLMCatalog.load(self.catalog_path)
		ok = _ok_response()

		def side_effect(**kwargs):
			model = kwargs.get("model")
			if model == "openrouter/free":
				raise RuntimeError(STEALTH_502)
			if model in ("qwen/qwen3-coder:free", "openrouter/qwen/qwen3-coder:free"):
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
		self.assertEqual(metrics["model_used"], "qwen/qwen3-coder:free")
		self.assertEqual(metrics["fallback_used"], 1.0)
		self.assertEqual(completion_mock.call_count, 2)
		self.assertEqual(len(fallback_hits), 1)
		self.assertEqual(fallback_hits[0]["model"], "qwen/qwen3-coder:free")

	@patch("libs.agent.llm.time.sleep")
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_rate_limit_sleeps_and_retries_same_model(self, completion_mock, _cost, sleep_mock):
		"""429 with try-again → sleep (capped) then retry same model succeeds."""
		catalog = FreeLLMCatalog.load(self.catalog_path)
		ok = _ok_response("ok-after-retry")
		calls = {"n": 0}

		def side_effect(**kwargs):
			calls["n"] += 1
			model = kwargs.get("model")
			if model in ("groq/llama-3.1-8b-instant",):
				if calls["n"] == 1:
					raise RuntimeError(GROQ_429)
				return ok
			raise AssertionError(f"unexpected model {model}")

		completion_mock.side_effect = side_effect

		with patch.dict(
			os.environ,
			{"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"},
			clear=False,
		):
			content, metrics = call_llm(
				"groq/llama-3.1-8b-instant",
				[{"role": "user", "content": "hi"}],
				configs_dir=self.configs_dir,
				catalog=catalog,
			)

		self.assertEqual(content, "ok-after-retry")
		self.assertEqual(metrics["model_used"], "groq/llama-3.1-8b-instant")
		self.assertEqual(metrics.get("fallback_used", 0.0), 0.0)
		self.assertEqual(completion_mock.call_count, 2)
		sleep_mock.assert_called()
		slept = float(sleep_mock.call_args[0][0])
		self.assertGreaterEqual(slept, 2.0)
		self.assertLessEqual(slept, 35.0)

	@patch("libs.agent.llm.time.sleep")
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_rate_limit_falls_through_to_next_free_model(self, completion_mock, _cost, sleep_mock):
		"""Persistent 429 after retries → next free catalog preset."""
		catalog = FreeLLMCatalog.load(self.catalog_path)
		ok = _ok_response("from-qwen")

		def side_effect(**kwargs):
			model = kwargs.get("model")
			if model == "openrouter/free":
				raise RuntimeError(OPENROUTER_429)
			if model in ("qwen/qwen3-coder:free", "openrouter/qwen/qwen3-coder:free"):
				return ok
			raise AssertionError(f"unexpected model {model}")

		completion_mock.side_effect = side_effect
		fallback_hits = []

		with patch.dict(
			os.environ,
			{"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"},
			clear=False,
		):
			content, metrics = call_llm(
				"openrouter/free",
				[{"role": "user", "content": "hi"}],
				configs_dir=self.configs_dir,
				catalog=catalog,
				on_fallback=fallback_hits.append,
			)

		self.assertEqual(content, "from-qwen")
		self.assertEqual(metrics["model_used"], "qwen/qwen3-coder:free")
		self.assertEqual(metrics["fallback_used"], 1.0)
		self.assertTrue(fallback_hits)
		# Must have retried same model at least once (sleep) before falling through
		sleep_mock.assert_called()
		self.assertGreaterEqual(completion_mock.call_count, 3)

	@patch("libs.agent.llm.time.sleep")
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_subsequent_call_uses_updated_model_after_fallback(self, completion_mock, _cost, sleep_mock):
		"""After fallback, shared on_fallback updates model; next call_llm uses it."""
		catalog = FreeLLMCatalog.load(self.catalog_path)
		shared = {"model": "openrouter/free"}
		seen_models = []

		def on_fallback(candidate):
			shared["model"] = str(candidate["model"])

		def side_effect(**kwargs):
			model = kwargs.get("model")
			seen_models.append(model)
			# First call: primary fails, fallback succeeds
			if model == "openrouter/free":
				raise RuntimeError(STEALTH_502)
			if model in ("qwen/qwen3-coder:free", "openrouter/qwen/qwen3-coder:free"):
				return _ok_response(f"ok:{model}")
			if model in ("groq/llama-3.1-8b-instant",):
				return _ok_response("ok:groq")
			raise AssertionError(f"unexpected model {model}")

		completion_mock.side_effect = side_effect

		with patch.dict(
			os.environ,
			{"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"},
			clear=False,
		):
			content1, metrics1 = call_llm(
				shared["model"],
				[{"role": "user", "content": "hi"}],
				configs_dir=self.configs_dir,
				catalog=catalog,
				on_fallback=on_fallback,
			)
			# Simulate controller applying fallback then calling again
			content2, metrics2 = call_llm(
				shared["model"],
				[{"role": "user", "content": "hi again"}],
				configs_dir=self.configs_dir,
				catalog=catalog,
				on_fallback=on_fallback,
			)

		self.assertEqual(metrics1["model_used"], "qwen/qwen3-coder:free")
		self.assertEqual(shared["model"], "qwen/qwen3-coder:free")
		self.assertEqual(metrics2["model_used"], "qwen/qwen3-coder:free")
		# Second call must not re-hit the dead openrouter/free primary
		self.assertNotEqual(seen_models[-1], "openrouter/free")
		self.assertIn("ok:", content1)
		self.assertIn("ok:", content2)

	@patch("libs.agent.llm.litellm.completion")
	def test_exhausted_raises_friendly_error(self, completion_mock):
		catalog = FreeLLMCatalog.load(self.catalog_path)
		completion_mock.side_effect = RuntimeError(STEALTH_502)

		with patch.dict(
			os.environ,
			{"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"},
			clear=False,
		):
			with self.assertRaises(FreeModelsExhaustedError) as ctx:
				call_llm(
					"openrouter/free",
					[{"role": "user", "content": "hi"}],
					configs_dir=self.configs_dir,
					catalog=catalog,
				)

		self.assertIn("/free", str(ctx.exception))
		self.assertIn("/model", str(ctx.exception))
		self.assertNotIn("sk-", str(ctx.exception))
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
		state = controller.run("say hi")
		self.assertEqual(state["status"], "FAILED")
		self.assertIn("/free", state["failure_reason"])
		self.assertIn("/model", state["failure_reason"])

	@patch("libs.agent.react_controller.call_llm")
	def test_rate_limit_exhaustion_is_clean_failure_not_crash(self, mock_llm):
		"""Rate-limit exhaustion surfaces as FAILED + tip, not unhandled traceback."""
		from libs.agent.react_controller import ReActController

		mock_llm.side_effect = FreeModelsExhaustedError(
			"All free / cheap models failed after trying: groq-llama. "
			"Last error: RateLimitError 429 try again in 2.5s. "
			"Use /free to list presets or /model <name> to switch models.",
			tried=["groq-llama"],
			last_error=RuntimeError(GROQ_429),
		)
		controller = ReActController(model_name="groq/llama-3.1-8b-instant", max_steps=2)
		# Must not raise — ReAct catches and reports cleanly
		state = controller.run("say hi")
		self.assertEqual(state["status"], "FAILED")
		self.assertIn("/free", state["failure_reason"])
		self.assertNotIn("Traceback", state["failure_reason"])

	@patch("libs.agent.llm.time.sleep")
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_controller_fallback_updates_specialist_models(self, completion_mock, _cost, sleep_mock):
		"""Controller on_fallback keeps coder/reviewer/debugger on the new model."""
		from libs.agent.react_controller import ReActController

		tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(tmpdir.cleanup)
		configs_dir = os.path.join(tmpdir.name, "configs")
		os.makedirs(configs_dir)
		for name, model in (
			("openrouter-free", "openrouter/free"),
			("openrouter-qwen-free", "qwen/qwen3-coder:free"),
		):
			_write_json(
				os.path.join(configs_dir, f"{name}.json"),
				{
					"provider": "openrouter",
					"api_base": "https://openrouter.ai/api/v1",
					"model": model,
					"temperature": 0.1,
					"max_tokens": 256,
				},
			)
		catalog_path = os.path.join(configs_dir, "free", "catalog.json")
		_write_json(
			catalog_path,
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
		)
		catalog = FreeLLMCatalog.load(catalog_path)

		# First think fails on openrouter/free, succeeds on qwen → finish
		def side_effect(**kwargs):
			model = kwargs.get("model")
			if model == "openrouter/free":
				raise RuntimeError(STEALTH_502)
			return _ok_response("Thought: done\nAction: finish\nAction Input: {\"summary\": \"ok\"}")

		completion_mock.side_effect = side_effect

		controller = ReActController(model_name="openrouter/free", max_steps=3)
		with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"}, clear=False):
			with patch("libs.agent.react_controller.call_llm", wraps=None) as _:
				# Drive via real call_llm path by patching the import used inside controller
				pass
			# Patch call_llm used by controller to the real one with our catalog
			from libs.agent import llm as llm_mod

			def call_with_catalog(model_name, messages, api_key=None, **kwargs):
				kwargs.setdefault("configs_dir", configs_dir)
				kwargs.setdefault("catalog", catalog)
				return llm_mod.call_llm(model_name, messages, api_key, **kwargs)

			with patch("libs.agent.react_controller.call_llm", side_effect=call_with_catalog):
				with patch("libs.agent.actions.coder.call_llm", side_effect=call_with_catalog):
					state = controller.run("finish quickly")

		self.assertEqual(state["status"], "COMPLETED")
		self.assertEqual(controller.model_name, "qwen/qwen3-coder:free")
		self.assertEqual(controller.coder.model_name, "qwen/qwen3-coder:free")
		self.assertEqual(controller.reviewer.model_name, "qwen/qwen3-coder:free")
		self.assertEqual(controller.debugger.model_name, "qwen/qwen3-coder:free")


class AgenticReplSlashCommandTests(unittest.TestCase):
	"""REPL command routing: /model with no args lists; unknown slash is not a ReAct task."""

	def _make_interp(self, inputs):
		from libs.interpreter_lib import Interpreter

		args = Namespace(
			lang="python",
			mode="code",
			model="local-model",
			save_code=False,
			exec=False,
			display_code=False,
			unsafe=False,
			sandbox=True,
			history=False,
			file=None,
			agent=False,
			agentic=True,
			gemini_style=True,
			cli=True,
			tui=False,
		)
		printed = []
		with patch.object(Interpreter, "__init__", lambda self, a: None):
			interp = Interpreter(args)
			interp.args = args
			interp.INTERPRETER_MODEL = "local-model"
			interp.INTERPRETER_MODEL_LABEL = "local-model"
			interp.INTERPRETER_PROMPT_FILE = False
			interp.UNSAFE_EXECUTION = False
			interp.MAX_REPAIR_ATTEMPTS = 3
			interp.terminal_ui = None
			interp.logger = type("L", (), {"error": lambda *a, **k: None})()
			interp.console = type(
				"C",
				(),
				{"print": lambda self, *a, **k: printed.append(" ".join(str(x) for x in a))},
			)()
			it = iter(inputs)
			interp._safe_input = lambda prompt, default="": next(it)
			return interp, printed

	def test_model_no_args_lists_presets_not_react_task(self):
		"""Bare /model opens TUI picker and must not start a ReAct task."""
		interp, printed = self._make_interp(["/model", "/exit"])
		mock_ui = MagicMock()
		mock_ui.select_free_model.return_value = "local-model"
		mock_ui.select_model.return_value = "local-model"
		with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
			with patch("libs.interpreter_lib.TerminalUI", return_value=mock_ui):
				with patch("os.path.isfile", return_value=True):
					from libs.interpreter_lib import Interpreter

					Interpreter.interpreter_agentic_main(interp)
					mock_ctrl.return_value.run.assert_not_called()
		self.assertTrue(
			mock_ui.select_free_model.called or mock_ui.select_model.called,
			"expected TUI model picker for bare /model",
		)
		joined = "\n".join(printed)
		self.assertNotIn("Usage: /model", joined)
		self.assertNotIn("ReAct agent starting", joined)

	def test_unknown_slash_mode_is_not_react_task(self):
		interp, printed = self._make_interp(["/foobar", "/exit"])
		with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
			from libs.interpreter_lib import Interpreter

			Interpreter.interpreter_agentic_main(interp)
			mock_ctrl.return_value.run.assert_not_called()
		joined = "\n".join(printed).lower()
		self.assertTrue(
			"unknown" in joined or "command" in joined or "/help" in joined,
			f"expected unknown-command tip, got: {printed}",
		)


if __name__ == "__main__":
	unittest.main()
