# -*- coding: utf-8 -*-
"""Regression tests for the no-args TUI wizard crashing on generate/project mode.

Bug: ``python interpreter.py`` with no CLI flags launches ``TerminalUI.launch()``.
If the arrow-key ``Mode`` selector is set to ``generate`` or ``project`` the wizard
used to finish (asking only interactive-charts/image/attach/mcp-server) and hand
off straight to ``run_codegen_cli`` -> ``resolve_codegen_task``, which unconditionally
raises ``ValueError`` because the wizard never collected ``--task``/``-f``. See
libs/code_generator.py resolve_codegen_task() and interpreter.py main().

Fix: ``TerminalUI.launch()`` now prompts for the task text (or a prompt file path)
whenever the selected mode is ``generate``/``project``, satisfying
``resolve_codegen_task``'s precondition before ``main()`` calls ``run_codegen_cli``.
"""

from __future__ import annotations

import os
import unittest
from argparse import Namespace
from unittest.mock import patch

from libs.terminal_ui import TerminalUI


class TestCollectCodegenTask(unittest.TestCase):
	"""Unit tests for TerminalUI._collect_codegen_task (new helper)."""

	def test_returns_existing_task_without_prompting(self):
		ui = TerminalUI()
		with patch.object(ui, "_prompt_optional") as mock_prompt:
			result = ui._collect_codegen_task(existing_task="already have one")
		mock_prompt.assert_not_called()
		self.assertEqual(result, {"task": "already have one", "file": None})

	def test_returns_existing_file_without_prompting(self):
		ui = TerminalUI()
		with patch.object(ui, "_prompt_optional") as mock_prompt:
			result = ui._collect_codegen_task(existing_file="prompt.txt")
		mock_prompt.assert_not_called()
		self.assertEqual(result, {"task": None, "file": "prompt.txt"})

	def test_prompts_for_task_when_missing(self):
		ui = TerminalUI()
		with patch.object(ui, "_prompt_optional", side_effect=["write a hello world script"]):
			result = ui._collect_codegen_task()
		self.assertEqual(result, {"task": "write a hello world script", "file": None})

	def test_falls_back_to_prompt_file_when_task_left_blank(self):
		ui = TerminalUI()
		with patch.object(ui, "_prompt_optional", side_effect=["", "prompt.txt"]):
			result = ui._collect_codegen_task()
		self.assertEqual(result, {"task": None, "file": "prompt.txt"})

	def test_retries_when_both_blank_then_succeeds(self):
		ui = TerminalUI()
		answers = ["", "", "", "", "finally a task"]
		with patch.object(ui, "_prompt_optional", side_effect=answers), \
			 patch.object(ui.console, "print"):
			result = ui._collect_codegen_task()
		self.assertEqual(result, {"task": "finally a task", "file": None})

	def test_exhausts_retries_and_exits_cleanly_instead_of_value_error(self):
		"""If the user truly never supplies a task/file, exit cleanly (no raw ValueError)."""
		ui = TerminalUI()
		with patch.object(ui, "_prompt_optional", side_effect=lambda *a, **k: ""), \
			 patch.object(ui.console, "print"):
			with self.assertRaises(SystemExit):
				ui._collect_codegen_task()


class TestLaunchCodegenTaskWiring(unittest.TestCase):
	"""Tests that TerminalUI.launch() wires the new task prompt in for generate/project."""

	def _base_args(self, **overrides):
		defaults = dict(
			exec=False, save_code=False, mode=None, model=None, task=None, output=None,
			lang="python", display_code=False, history=False, upgrade=False, file=None,
			agentic=False, gemini_style=False, free=False, list_free=False,
			sandbox="subprocess", sandbox_backend="subprocess", unsafe=False, timeout=30,
			safety="standard", cli=False, tui=True, agent=False, yes=False, yolo=False,
			mcp_server=None, stream=True, image=None, search=False,
			search_provider="duckduckgo", search_api_key=None, output_format=None,
			no_color=False, session=None, list_sessions=False, delete_session=None,
			new_session=False, attach=None, ollama=None, list_ollama=False, local=False,
			eda=None, interactive_charts=False, science=False, plot_theme=None,
			report=False, no_auto_install=False,
		)
		defaults.update(overrides)
		return Namespace(**defaults)

	def _stub_everything_except_mode_and_task(self, ui, *, mode, task_answer=""):
		"""Drive launch() with every selector defaulted except Mode and the new task prompt."""

		def select_option(title, options, default, help_text=None):
			if title.startswith("Mode"):
				return mode
			return default if default in options else options[0]

		def select_boolean(title, default=False):
			return default

		def prompt_ask(prompt, default=""):
			lowered = str(prompt).lower()
			if "task description" in lowered:
				return task_answer
			if "prompt file path instead" in lowered:
				return ""
			return default

		ui._select_option = select_option
		ui._select_boolean = select_boolean
		ui.select_model = lambda default_model=None: default_model or "gpt-4o-mini"
		ui.select_free_model = lambda default_model=None: default_model or "gpt-4o-mini"
		return patch("libs.terminal_ui.Prompt.ask", side_effect=prompt_ask)

	def test_launch_generate_mode_prompts_for_task_and_sets_args_task(self):
		ui = TerminalUI()
		args = self._base_args()
		with self._stub_everything_except_mode_and_task(ui, mode="generate", task_answer="write a binary search"):
			with patch.object(ui.utility_manager, "clear_screen"), patch.object(ui.console, "print"):
				result = ui.launch(args)

		self.assertEqual(result.mode, "generate")
		self.assertEqual(result.task, "write a binary search")
		self.assertIsNone(result.file)

	def test_launch_project_mode_prompts_for_task_and_sets_args_task(self):
		ui = TerminalUI()
		args = self._base_args()
		with self._stub_everything_except_mode_and_task(ui, mode="project", task_answer="scaffold a flask app"):
			with patch.object(ui.utility_manager, "clear_screen"), patch.object(ui.console, "print"):
				result = ui.launch(args)

		self.assertEqual(result.mode, "project")
		self.assertEqual(result.task, "scaffold a flask app")

	def test_launch_code_mode_never_prompts_for_task(self):
		"""Non-codegen modes must not gain a new required prompt (no regression)."""
		ui = TerminalUI()
		args = self._base_args()

		def select_option(title, options, default, help_text=None):
			return default if default in options else options[0]

		def select_boolean(title, default=False):
			return default

		def prompt_ask(prompt, default=""):
			if "task description" in str(prompt).lower():
				raise AssertionError("code mode must not prompt for a codegen task")
			return default

		ui._select_option = select_option
		ui._select_boolean = select_boolean
		ui.select_model = lambda default_model=None: "gpt-4o-mini"
		ui.select_free_model = lambda default_model=None: "gpt-4o-mini"

		with patch("libs.terminal_ui.Prompt.ask", side_effect=prompt_ask):
			with patch.object(ui.utility_manager, "clear_screen"), patch.object(ui.console, "print"):
				result = ui.launch(args)

		self.assertEqual(result.mode, "code")
		self.assertFalse(hasattr(result, "task") and result.task)

	def test_launch_generate_mode_reuses_preexisting_task_without_reprompting(self):
		"""If --task was already supplied (e.g. combined with --tui), don't ask again."""
		ui = TerminalUI()
		args = self._base_args(task="already provided via CLI")

		def prompt_ask(prompt, default=""):
			if "task description" in str(prompt).lower() or "prompt file path instead" in str(prompt).lower():
				raise AssertionError("must not re-prompt when --task was already provided")
			return default

		with self._stub_everything_except_mode_and_task(ui, mode="generate"):
			with patch("libs.terminal_ui.Prompt.ask", side_effect=prompt_ask):
				with patch.object(ui.utility_manager, "clear_screen"), patch.object(ui.console, "print"):
					result = ui.launch(args)

		self.assertEqual(result.task, "already provided via CLI")


class TestNoArgsWizardGenerateModeRegression(unittest.TestCase):
	"""End-to-end reproduction of the exact reported bug via interpreter.main()."""

	def test_no_args_wizard_generate_mode_with_defaults_does_not_raise_value_error(self):
		"""python interpreter.py (no argv) -> wizard picks 'generate' + defaults elsewhere
		+ a task at the (new) task prompt -> must NOT raise the reported ValueError."""
		import interpreter as interpreter_mod

		def fake_select_option(self, title, options, default, help_text=None):
			if title.startswith("Mode"):
				return "generate"
			return default if default in options else options[0]

		def fake_select_boolean(self, title, default=False):
			return default

		def fake_prompt_optional(self, title, default=""):
			if title.startswith("Task description"):
				return "write a hello world function"
			return default or ""

		def fake_completion(model, **kwargs):
			from types import SimpleNamespace

			return SimpleNamespace(
				choices=[SimpleNamespace(message=SimpleNamespace(content="```python\nprint('hi')\n```"))]
			)

		written = {}

		def fake_write_text(path, content):
			written["path"] = path
			written["content"] = content
			return os.path.abspath(path)

		with patch.object(TerminalUI, "_select_option", fake_select_option), \
			 patch.object(TerminalUI, "_select_boolean", fake_select_boolean), \
			 patch.object(TerminalUI, "_prompt_optional", fake_prompt_optional), \
			 patch("libs.terminal_ui.UtilityManager.clear_screen", lambda self: None), \
			 patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None), \
			 patch("litellm.completion", side_effect=fake_completion), \
			 patch("libs.code_generator.CodeGenerator._write_text", side_effect=fake_write_text):
			try:
				interpreter_mod.main(["interpreter.py"])
			except ValueError as exc:
				self.fail(f"main() raised the reported ValueError instead of completing codegen: {exc}")

		self.assertIn("print('hi')", written.get("content", ""))


if __name__ == "__main__":
	unittest.main()
