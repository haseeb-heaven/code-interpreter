"""Tests for free LLM catalog and Gemini-CLI-style flags (mocked, no live APIs)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch

import interpreter as interpreter_entry
from libs.free_llms import FreeLLMCatalog, FreeModelEntry, resolve_free_model


class FreeModelEntryTests(unittest.TestCase):
	def test_from_dict_requires_config(self):
		with self.assertRaises(ValueError):
			FreeModelEntry.from_dict({})

	def test_local_always_available(self):
		entry = FreeModelEntry(
			id="local-model",
			config="local-model",
			provider="local",
			env_key=None,
			tier="local",
		)
		self.assertTrue(entry.is_available(environ={}))

	def test_cloud_requires_env_key(self):
		entry = FreeModelEntry(
			id="openrouter-free",
			config="openrouter-free",
			provider="openrouter",
			env_key="OPENROUTER_API_KEY",
			tier="free",
		)
		self.assertFalse(entry.is_available(environ={}))
		self.assertTrue(entry.is_available(environ={"OPENROUTER_API_KEY": "sk-or-test"}))


class FreeLLMCatalogTests(unittest.TestCase):
	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmpdir.cleanup)
		self.configs_dir = os.path.join(self._tmpdir.name, "configs")
		os.makedirs(self.configs_dir)
		# Minimal config files referenced by catalog
		for name in ("openrouter-free", "groq-llama-3.1-8b", "local-model"):
			with open(os.path.join(self.configs_dir, f"{name}.json"), "w", encoding="utf-8") as handle:
				json.dump({"model": name}, handle)

		catalog_dir = os.path.join(self.configs_dir, "free")
		os.makedirs(catalog_dir)
		self.catalog_path = os.path.join(catalog_dir, "catalog.json")
		payload = {
			"version": 1,
			"models": [
				{
					"id": "openrouter-free",
					"config": "openrouter-free",
					"provider": "openrouter",
					"env_key": "OPENROUTER_API_KEY",
					"tier": "free",
					"notes": "OR free",
				},
				{
					"id": "groq-llama-3.1-8b",
					"config": "groq-llama-3.1-8b",
					"provider": "groq",
					"env_key": "GROQ_API_KEY",
					"tier": "free_tier",
					"notes": "Groq",
				},
				{
					"id": "local-model",
					"config": "local-model",
					"provider": "local",
					"env_key": None,
					"tier": "local",
					"notes": "Local",
				},
			],
		}
		with open(self.catalog_path, "w", encoding="utf-8") as handle:
			json.dump(payload, handle)

	def test_load_catalog(self):
		catalog = FreeLLMCatalog.load(self.catalog_path)
		self.assertEqual(len(catalog), 3)
		self.assertIn("openrouter-free", catalog.list_ids())

	def test_available_filters_by_env(self):
		catalog = FreeLLMCatalog.load(self.catalog_path)
		# Only local without keys
		ready = catalog.available(environ={}, configs_dir=self.configs_dir)
		self.assertEqual([e.config for e in ready], ["local-model"])

		ready = catalog.available(
			environ={"GROQ_API_KEY": "gsk-test"},
			configs_dir=self.configs_dir,
		)
		self.assertEqual([e.config for e in ready], ["groq-llama-3.1-8b", "local-model"])

	def test_pick_default_prefers_order(self):
		catalog = FreeLLMCatalog.load(self.catalog_path)
		picked = catalog.pick_default(
			environ={"OPENROUTER_API_KEY": "sk-or", "GROQ_API_KEY": "gsk"},
			configs_dir=self.configs_dir,
			preferred=["groq-llama-3.1-8b"],
		)
		self.assertEqual(picked, "groq-llama-3.1-8b")

	def test_format_table_contains_tip(self):
		catalog = FreeLLMCatalog.load(self.catalog_path)
		table = catalog.format_table(environ={}, configs_dir=self.configs_dir)
		self.assertIn("Free / cheap LLM presets", table)
		self.assertIn("--gemini-style", table)
		self.assertIn("local-model", table)

	def test_resolve_free_model_respects_explicit(self):
		catalog = FreeLLMCatalog.load(self.catalog_path)
		self.assertEqual(
			resolve_free_model(explicit_model="gpt-4o", prefer_free=True, catalog=catalog),
			"gpt-4o",
		)

	def test_resolve_free_model_picks_when_prefer_free(self):
		catalog = FreeLLMCatalog.load(self.catalog_path)
		picked = resolve_free_model(
			prefer_free=True,
			environ={},
			catalog=catalog,
			configs_dir=self.configs_dir,
		)
		self.assertEqual(picked, "local-model")

	def test_repo_catalog_loads_and_has_openrouter_free(self):
		catalog = FreeLLMCatalog.load()
		self.assertGreaterEqual(len(catalog), 5)
		self.assertIsNotNone(catalog.get("openrouter-free"))
		self.assertIsNotNone(catalog.get("local-model"))
		self.assertIsNotNone(catalog.get("gemini-2.5-flash"))


class GeminiStyleFlagTests(unittest.TestCase):
	def test_parser_has_gemini_style_and_free_flags(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--gemini-style"])
		self.assertTrue(args.gemini_style)
		args = parser.parse_args(["--free", "--cli"])
		self.assertTrue(args.free)
		args = parser.parse_args(["--list-free"])
		self.assertTrue(args.list_free)

	@patch("interpreter._get_default_model", return_value="gpt-4o")
	@patch("libs.free_llms.resolve_free_model", return_value="openrouter-free")
	def test_prepare_args_gemini_style_enables_agentic_and_free_model(
		self, mock_resolve, _mock_default
	):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--gemini-style"])
		prepared = interpreter_entry.prepare_args(args, ["interpreter.py", "--gemini-style"])
		self.assertTrue(prepared.agentic)
		self.assertTrue(prepared.free)
		self.assertTrue(prepared.cli)
		self.assertFalse(prepared.tui)
		self.assertEqual(prepared.model, "openrouter-free")
		mock_resolve.assert_called()

	@patch("interpreter._get_default_model", return_value="gpt-4o")
	@patch("libs.free_llms.resolve_free_model", return_value="groq-llama-3.1-8b")
	def test_prepare_args_free_without_model(self, mock_resolve, _mock_default):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli", "--free"])
		prepared = interpreter_entry.prepare_args(args, ["interpreter.py", "--cli", "--free"])
		self.assertEqual(prepared.model, "groq-llama-3.1-8b")
		mock_resolve.assert_called()

	@patch("interpreter._get_default_model", return_value="gpt-4o")
	def test_prepare_args_free_keeps_explicit_model(self, _mock_default):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli", "--free", "-m", "gemini-2.5-flash"])
		prepared = interpreter_entry.prepare_args(
			args, ["interpreter.py", "--cli", "--free", "-m", "gemini-2.5-flash"]
		)
		self.assertEqual(prepared.model, "gemini-2.5-flash")

	def test_list_free_prints_and_exits(self):
		buf = io.StringIO()
		with patch("sys.stdout", buf):
			interpreter_entry.main(["interpreter.py", "--list-free"])
		out = buf.getvalue()
		self.assertIn("Free / cheap LLM presets", out)
		self.assertIn("openrouter-free", out)


class AgenticReplCommandTests(unittest.TestCase):
	def test_agentic_repl_handles_exit_without_react(self):
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

		with patch.object(Interpreter, "__init__", lambda self, a: None):
			interp = Interpreter(args)
			interp.args = args
			interp.INTERPRETER_MODEL = "local-model"
			interp.INTERPRETER_MODEL_LABEL = "local-model"
			interp.INTERPRETER_PROMPT_FILE = False
			interp.UNSAFE_EXECUTION = False
			interp.MAX_REPAIR_ATTEMPTS = 3
			interp.logger = type("L", (), {"error": lambda *a, **k: None})()
			interp.console = type(
				"C",
				(),
				{"print": lambda self, *a, **k: None},
			)()

			inputs = iter(["/exit"])
			interp._safe_input = lambda prompt, default="": next(inputs)

			with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
				Interpreter.interpreter_agentic_main(interp)
				mock_ctrl.return_value.run.assert_not_called()


if __name__ == "__main__":
	unittest.main()
