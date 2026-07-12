"""TDD: AutoLoop free-catalog fallback + /model TUI picker.

Covers (mocked, no live keys):
1. call_llm on free-models-per-day skips remaining OpenRouter free → Groq/Gemini
2. AutoLoop uses same free-catalog fallback (429 / Stealth 502 / daily quota)
3. /model with no args opens TerminalUI model picker (not bare usage text)
4. /model with invalid name opens picker and lists valid config names
5. /model gemini-2.5-flash resolves configs/<name>.json (not litellm id alone)
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
from libs.free_llms import FreeLLMCatalog, is_daily_free_quota_exhausted


DAILY_QUOTA = (
	"litellm.RateLimitError: OpenrouterException - "
	'{"error":{"message":"Rate limit exceeded: free-models-per-day. '
	'Remaining: 0","code":429}}'
)

STEALTH_502 = (
	'litellm.APIError: OpenrouterException - '
	'{"error":{"message":"Invalid URL: ","code":502,'
	'"metadata":{"provider_name":"Stealth"}}}'
)

OPENROUTER_429 = (
	"litellm.RateLimitError: RateLimitError: OpenrouterException - "
	'{"error":{"message":"Rate limit exceeded: try again in 1.2s","code":429}}'
)


def _ok_response(text: str = "ok"):
	return SimpleNamespace(
		choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=None))],
		usage=SimpleNamespace(total_tokens=3),
	)


def _toml_scalar(value) -> str:
	if isinstance(value, bool):
		return "true" if value else "false"
	if isinstance(value, (int, float)):
		return str(value)
	return json.dumps(str(value))


def _write_models_toml(configs_dir: str, models: dict, free_catalog=None) -> str:
	"""Write a minimal ``models.toml`` fixture for tests (replaces per-model JSON files)."""
	os.makedirs(configs_dir, exist_ok=True)
	lines = []
	for name, payload in models.items():
		lines.append(f'[models.{json.dumps(str(name))}]')
		for key, value in payload.items():
			lines.append(f"{key} = {_toml_scalar(value)}")
		lines.append("")
	for entry in free_catalog or []:
		lines.append("[[free_catalog]]")
		for key, value in entry.items():
			lines.append(f"{key} = {_toml_scalar(value)}")
		lines.append("")
	path = os.path.join(configs_dir, "models.toml")
	with open(path, "w", encoding="utf-8") as handle:
		handle.write("\n".join(lines))
	return path


class DailyQuotaSkipOpenRouterTests(unittest.TestCase):
	"""On free-models-per-day, skip remaining OR free and land on Groq."""

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
		free_catalog = [
			{
				"id": "openrouter-free",
				"model_key": "openrouter-free",
				"provider": "openrouter",
				"env_key": "OPENROUTER_API_KEY",
				"tier": "free",
			},
			{
				"id": "openrouter-qwen-free",
				"model_key": "openrouter-qwen-free",
				"provider": "openrouter",
				"env_key": "OPENROUTER_API_KEY",
				"tier": "free",
			},
			{
				"id": "groq-llama",
				"model_key": "groq-llama",
				"provider": "groq",
				"env_key": "GROQ_API_KEY",
				"tier": "free_tier",
			},
		]
		self.catalog_path = _write_models_toml(self.configs_dir, specs, free_catalog)
		self.catalog = FreeLLMCatalog.load(self.catalog_path)
		self.env = {"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"}

	def test_daily_quota_detector(self):
		self.assertTrue(is_daily_free_quota_exhausted(RuntimeError(DAILY_QUOTA)))

	def test_daily_quota_skips_remaining_openrouter_free(self):
		tried_models = []

		def fake_completion(**kwargs):
			model = kwargs.get("model") or ""
			tried_models.append(model)
			if "openrouter" in model.lower() or ":free" in model.lower() or model == "openrouter/free":
				# Primary OR free hits daily quota; sibling OR must not be retried long.
				raise RuntimeError(DAILY_QUOTA)
			return _ok_response("from-groq")

		with patch.dict(os.environ, self.env, clear=False):
			with patch("libs.agent.llm.litellm.completion", side_effect=fake_completion):
				content, metrics = call_llm(
					"openrouter-free",
					[{"role": "user", "content": "hi"}],
					enable_free_fallback=True,
					configs_dir=self.configs_dir,
					catalog=self.catalog,
					rate_limit_retries=2,
					sleep_fn=lambda _s: None,
				)

		self.assertEqual(content, "from-groq")
		self.assertEqual(metrics.get("model_used"), "groq/llama-3.1-8b-instant")
		# Must not spend attempts on the sibling OR free after daily quota.
		joined = " | ".join(tried_models).lower()
		self.assertNotIn("qwen3-coder", joined)
		self.assertTrue(
			any("groq" in m.lower() or "llama-3.1" in m.lower() for m in tried_models),
			f"expected Groq attempt, got {tried_models}",
		)

	def test_tool_use_unsupported_skips_remaining_openrouter_free(self):
		"""OR free 'No endpoints found that support tool use' → skip OR free → Groq."""
		from libs.agent.llm import complete_with_free_fallback
		from libs.free_llms import is_tool_use_unsupported

		tool_err = RuntimeError(
			"Error code: 404 - {'error': {'message': "
			"'No endpoints found that support tool use. To learn more about provider "
			"routing, visit: https://openrouter.ai/docs/provider-routing', "
			"'code': 404}}"
		)
		self.assertTrue(is_tool_use_unsupported(tool_err))

		tried_models = []
		fake_tools = [
			{
				"type": "function",
				"function": {"name": "read_file", "parameters": {"type": "object"}},
			}
		]

		def fake_completion(**kwargs):
			model = kwargs.get("model") or ""
			tried_models.append(model)
			if "openrouter" in model.lower() or ":free" in model.lower() or model == "openrouter/free":
				raise tool_err
			# Groq accepts tools
			self.assertIsNotNone(kwargs.get("tools"))
			return _ok_response("from-groq-with-tools")

		with patch.dict(os.environ, self.env, clear=False):
			with patch("libs.agent.llm.litellm.completion", side_effect=fake_completion):
				response, metrics = complete_with_free_fallback(
					"openrouter-free",
					[{"role": "user", "content": "read a file"}],
					tools=fake_tools,
					tool_choice="auto",
					enable_free_fallback=True,
					configs_dir=self.configs_dir,
					catalog=self.catalog,
					rate_limit_retries=1,
					sleep_fn=lambda _s: None,
				)

		content = response.choices[0].message.content
		self.assertEqual(content, "from-groq-with-tools")
		self.assertEqual(metrics.get("model_used"), "groq/llama-3.1-8b-instant")
		joined = " | ".join(tried_models).lower()
		self.assertNotIn("qwen3-coder", joined)


class AutoLoopFreeFallbackTests(unittest.TestCase):
	"""AutoLoop / YOLO path must not hard-fail on OR free daily quota / 502 / 429."""

	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmpdir.cleanup)
		self.configs_dir = os.path.join(self._tmpdir.name, "configs")
		os.makedirs(self.configs_dir)
		models = {
			"openrouter-free": {
				"provider": "openrouter",
				"api_base": "https://openrouter.ai/api/v1",
				"model": "openrouter/free",
				"temperature": 0.1,
				"max_tokens": 1024,
			},
			"openrouter-qwen-free": {
				"provider": "openrouter",
				"api_base": "https://openrouter.ai/api/v1",
				"model": "qwen/qwen3-coder:free",
				"temperature": 0.1,
				"max_tokens": 1024,
			},
			"groq-llama": {
				"provider": "groq",
				"model": "groq/llama-3.1-8b-instant",
				"temperature": 0.1,
				"max_tokens": 1024,
			},
		}
		free_catalog = [
			{
				"id": "openrouter-free",
				"model_key": "openrouter-free",
				"provider": "openrouter",
				"env_key": "OPENROUTER_API_KEY",
				"tier": "free",
			},
			{
				"id": "openrouter-qwen-free",
				"model_key": "openrouter-qwen-free",
				"provider": "openrouter",
				"env_key": "OPENROUTER_API_KEY",
				"tier": "free",
			},
			{
				"id": "groq-llama",
				"model_key": "groq-llama",
				"provider": "groq",
				"env_key": "GROQ_API_KEY",
				"tier": "free_tier",
			},
		]
		registry_path = _write_models_toml(self.configs_dir, models, free_catalog)
		self.catalog = FreeLLMCatalog.load(registry_path)
		self.env = {"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"}

	def _run_loop(self, side_effect_exc: Exception):
		from libs.agent.auto_loop import AutonomousAgentLoop

		attempted = []

		def fake_litellm(**kwargs):
			model = str(kwargs.get("model") or "")
			attempted.append(model)
			if "openrouter" in model.lower() or model.endswith("/free") or ":free" in model:
				raise side_effect_exc
			return _ok_response("autoloop-fallback-ok")

		with patch.dict(os.environ, self.env, clear=False):
			with patch("libs.agent.llm.litellm.completion", side_effect=fake_litellm):
				with patch("litellm.completion", side_effect=fake_litellm):
					loop = AutonomousAgentLoop(
						model="openrouter-free",
						auto_mode=True,
						enable_free_fallback=True,
						configs_dir=self.configs_dir,
						catalog=self.catalog,
						api_key=None,
						sleep_fn=lambda _s: None,
						rate_limit_retries=2,
					)
					result = loop.run("say hi")
		return result, attempted

	def _assert_jumped_to_groq_without_or_siblings(self, result, attempted):
		"""Daily-quota / OR RateLimit must not hard-stop or burn sibling OR free."""
		self.assertEqual(result, "autoloop-fallback-ok", result)
		self.assertFalse(
			str(result).startswith("[LLM Error] litellm.RateLimitError"),
			f"bare RateLimit hard-stop without fallback: {result!r}",
		)
		joined = " | ".join(attempted).lower()
		self.assertNotIn("qwen3-coder", joined, f"burned OR sibling: {attempted}")
		self.assertTrue(
			any("groq" in m.lower() or "llama-3.1-8b-instant" in m.lower() for m in attempted),
			f"expected Groq next, got {attempted}",
		)
		# Immediate jump: primary OR then Groq (no other OR free in between).
		non_primary = [m for m in attempted if "openrouter/free" not in m.lower()]
		self.assertTrue(non_primary, attempted)
		self.assertTrue(
			"groq" in non_primary[0].lower() or "llama-3.1" in non_primary[0].lower(),
			f"next model after OR should be Groq, got {attempted}",
		)

	def test_autoloop_falls_back_on_daily_quota(self):
		result, attempted = self._run_loop(RuntimeError(DAILY_QUOTA))
		self._assert_jumped_to_groq_without_or_siblings(result, attempted)

	def test_autoloop_falls_back_on_stealth_502(self):
		result, attempted = self._run_loop(RuntimeError(STEALTH_502))
		self.assertEqual(result, "autoloop-fallback-ok")
		self.assertTrue(any("groq" in m.lower() or "llama" in m.lower() for m in attempted), attempted)

	def test_autoloop_falls_back_on_openrouter_429(self):
		result, attempted = self._run_loop(RuntimeError(OPENROUTER_429))
		self.assertEqual(result, "autoloop-fallback-ok")
		self.assertTrue(any("groq" in m.lower() or "llama" in m.lower() for m in attempted), attempted)

	def test_autoloop_ratelimit_free_models_per_day_jumps_to_groq(self):
		"""Regression: litellm.RateLimitError(free-models-per-day) must rotate, not hard-stop."""
		from litellm.exceptions import RateLimitError

		exc = RateLimitError(
			message="Rate limit exceeded: free-models-per-day. Remaining: 0",
			model="openrouter/free",
			llm_provider="openrouter",
		)
		result, attempted = self._run_loop(exc)
		self._assert_jumped_to_groq_without_or_siblings(result, attempted)

	def test_autoloop_ratelimit_provider_returned_error_skips_or_siblings(self):
		"""Provider returned error on OR free must not burn remaining OR :free slots."""
		from litellm.exceptions import RateLimitError

		exc = RateLimitError(
			message="Provider returned error",
			model="openrouter/free",
			llm_provider="openrouter",
		)
		result, attempted = self._run_loop(exc)
		self._assert_jumped_to_groq_without_or_siblings(result, attempted)


class ResolveModelConfigNameTests(unittest.TestCase):
	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmpdir.cleanup)
		self.configs_dir = self._tmpdir.name
		_write_models_toml(
			self.configs_dir,
			{
				"gemini-2.5-flash": {"model": "gemini/gemini-2.5-flash", "temperature": 0.1, "max_tokens": 2048},
				"gemini-2.5-pro": {"model": "gemini/gemini-2.5-pro", "temperature": 0.1, "max_tokens": 3072},
			},
		)

	def test_resolves_config_basename(self):
		from libs.free_llms import resolve_model_config_name

		self.assertEqual(
			resolve_model_config_name("gemini-2.5-flash", configs_dir=self.configs_dir),
			"gemini-2.5-flash",
		)

	def test_resolves_litellm_id_to_config_when_unique(self):
		from libs.free_llms import resolve_model_config_name

		self.assertEqual(
			resolve_model_config_name("gemini/gemini-2.5-pro", configs_dir=self.configs_dir),
			"gemini-2.5-pro",
		)

	def test_unknown_returns_none(self):
		from libs.free_llms import resolve_model_config_name

		self.assertIsNone(
			resolve_model_config_name("not-a-real-model", configs_dir=self.configs_dir)
		)


class ModelSlashOpensTuiTests(unittest.TestCase):
	"""Agentic + auto REPLS: bare /model opens TUI picker."""

	def _make_interp(self, inputs, *, agentic=True, auto=False):
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
			agentic=agentic,
			gemini_style=True,
			free=True,
			cli=True,
			tui=False,
			yolo=True,
			mcp_server=None,
			search=False,
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
			interp.config_values = {"model": "local-model"}
			interp.terminal_ui = None
			interp.logger = type("L", (), {"error": lambda *a, **k: None, "info": lambda *a, **k: None})()
			interp.console = type(
				"C",
				(),
				{"print": lambda self, *a, **k: printed.append(" ".join(str(x) for x in a))},
			)()
			it = iter(inputs)
			interp._safe_input = lambda prompt, default="": next(it)
			interp.initialize_client = MagicMock()
			return interp, printed

	def test_agentic_model_no_args_opens_tui_not_usage(self):
		interp, printed = self._make_interp(["/model", "/exit"], agentic=True)
		mock_ui = MagicMock()
		mock_ui.select_free_model.return_value = "gemini-2.5-flash"
		mock_ui.select_model.return_value = "gemini-2.5-flash"

		with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
			with patch("libs.interpreter_lib.TerminalUI", return_value=mock_ui):
				with patch("os.path.isfile", return_value=True):
					from libs.interpreter_lib import Interpreter

					Interpreter.interpreter_agentic_main(interp)

		joined = "\n".join(printed)
		self.assertNotIn("Usage: /model", joined)
		self.assertTrue(
			mock_ui.select_free_model.called or mock_ui.select_model.called,
			"expected TUI model picker",
		)
		mock_ctrl.return_value.run.assert_not_called()

	def test_agentic_invalid_model_opens_tui(self):
		interp, printed = self._make_interp(["/model nope-model", "/exit"], agentic=True)
		mock_ui = MagicMock()
		mock_ui.select_free_model.return_value = "gemini-2.5-flash"
		mock_ui.select_model.return_value = "gemini-2.5-flash"

		with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
			with patch("libs.interpreter_lib.TerminalUI", return_value=mock_ui):
				with patch(
					"libs.free_llms.resolve_model_config_name",
					side_effect=lambda name, **k: None if "nope" in name else name,
				):
					with patch("os.path.isfile", return_value=True):
						from libs.interpreter_lib import Interpreter

						Interpreter.interpreter_agentic_main(interp)

		joined = "\n".join(printed).lower()
		self.assertTrue(
			"does not" in joined
			or "invalid" in joined
			or "not a valid" in joined
			or "not exist" in joined,
			printed,
		)
		self.assertTrue(mock_ui.select_free_model.called or mock_ui.select_model.called)
		mock_ctrl.return_value.run.assert_not_called()

	def test_agentic_valid_config_name_switches(self):
		interp, printed = self._make_interp(["/model gemini-2.5-flash", "/exit"], agentic=True)

		with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
			with patch(
				"libs.free_llms.resolve_model_config_name",
				return_value="gemini-2.5-flash",
			):
				with patch("os.path.isfile", return_value=True):
					from libs.interpreter_lib import Interpreter

					Interpreter.interpreter_agentic_main(interp)

		self.assertEqual(interp.INTERPRETER_MODEL, "gemini-2.5-flash")
		joined = "\n".join(printed).lower()
		self.assertIn("gemini-2.5-flash", joined)
		mock_ctrl.assert_called()
		# Second controller construction is the switch (first is startup)
		self.assertGreaterEqual(mock_ctrl.call_count, 2)

	def test_help_mentions_model_opens_picker(self):
		interp, printed = self._make_interp(["/help", "/exit"], agentic=True)
		with patch("libs.agent.react_controller.ReActController"):
			from libs.interpreter_lib import Interpreter

			Interpreter.interpreter_agentic_main(interp)
		joined = "\n".join(printed).lower()
		self.assertIn("/model", joined)
		self.assertTrue("picker" in joined or "select" in joined or "tui" in joined or "interactive" in joined)


if __name__ == "__main__":
	unittest.main()
