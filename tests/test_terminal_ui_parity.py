"""Unit tests for TUI ↔ CLI option parity (selectors + Namespace wiring)."""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from libs.terminal_ui import TerminalUI, WORKFLOW_CLASSIC, WORKFLOW_AGENTIC, WORKFLOW_AGENT, WORKFLOW_GEMINI


def _base_args(**overrides):
	"""Minimal argparse-like Namespace as prepare_args would pass into TUI.launch."""
	defaults = dict(
		exec=False,
		save_code=False,
		mode=None,
		model=None,
		task=None,
		output=None,
		lang="python",
		display_code=False,
		history=False,
		upgrade=False,
		file=None,
		agentic=False,
		gemini_style=False,
		free=False,
		list_free=False,
		sandbox="subprocess",
		sandbox_backend="subprocess",
		unsafe=False,
		timeout=30,
		safety="standard",
		cli=False,
		tui=True,
		agent=False,
		yes=False,
		yolo=False,
		mcp_server=None,
		stream=True,
		image=None,
		search=False,
		search_provider="duckduckgo",
		search_api_key=None,
		output_format=None,
		no_color=False,
		session=None,
		list_sessions=False,
		delete_session=None,
		new_session=False,
		attach=None,
		ollama=None,
		list_ollama=False,
		local=False,
		eda=None,
		interactive_charts=False,
		science=False,
		plot_theme=None,
		report=False,
		no_auto_install=False,
	)
	defaults.update(overrides)
	return Namespace(**defaults)


class TestTerminalUIModeAndWorkflowOptions(unittest.TestCase):
	def test_select_mode_includes_codegen_modes(self):
		ui = TerminalUI()
		with patch.object(ui, "_select_option", side_effect=lambda *a, **k: a[1][0]) as mock_sel:
			ui.select_mode("code")
		options = mock_sel.call_args[0][1]
		for expected in ("code", "chat", "script", "command", "vision", "generate", "project"):
			self.assertIn(expected, options)

	def test_select_workflow_options(self):
		ui = TerminalUI()
		with patch.object(ui, "_select_option", side_effect=lambda *a, **k: a[1][0]) as mock_sel:
			ui.select_workflow(WORKFLOW_CLASSIC)
		options = mock_sel.call_args[0][1]
		self.assertEqual(
			options,
			[WORKFLOW_CLASSIC, WORKFLOW_AGENTIC, WORKFLOW_AGENT, WORKFLOW_GEMINI],
		)

	def test_select_language_includes_r(self):
		ui = TerminalUI()
		with patch.object(ui, "_select_option", side_effect=lambda *a, **k: a[1][0]) as mock_sel:
			ui.select_language("python")
		self.assertIn("r", mock_sel.call_args[0][1])


class TestTerminalUILaunchWiring(unittest.TestCase):
	def _stub_launch_selectors(self, ui, *, mode="code", workflow=WORKFLOW_AGENTIC, free=True,
							   model="openrouter-free", language="python",
							   sandbox="subprocess", safety="standard",
							   display_code=True, execute_code=False, save_code=False,
							   history=True, stream=True, search=True,
							   output_format="markdown", session="my-session",
							   yolo=False, yes=False, science=False,
							   interactive_charts=False, configure_more=False,
							   image=None, attach=None, mcp=None):
		"""Drive launch() through mocked selectors / prompts.

		Assumes ``_base_args()`` defaults (display/exec/save/history all False), so those
		selectors are always asked when mode warrants it. Answers come from the kwargs.
		"""
		gemini = workflow == WORKFLOW_GEMINI
		bool_queue = []
		if not gemini:
			bool_queue.append(free)
		if mode in ["code", "script", "command", "generate", "project"]:
			bool_queue.append(display_code)
		if mode == "code":
			bool_queue.append(execute_code)
		if mode in ["code", "script", "command"]:
			bool_queue.append(save_code)
		bool_queue.append(history)
		if not gemini:
			bool_queue.append(stream)
		bool_queue.append(search)
		bool_queue.append(configure_more)
		if configure_more:
			bool_queue.extend([yolo, yes, science, interactive_charts])

		option_map = {
			"Mode": mode,
			"Workflow": workflow,
			"Model": model,
			"Free / cheap model": model,
			"Language": language,
			"Sandbox": sandbox,
			"Safety level": safety,
			"Output format": (
				"auto (TTY default)" if not output_format else output_format
			),
		}

		def select_option(title, options, default, help_text=None):
			for key, value in option_map.items():
				if title.startswith(key) or key in title:
					return value if value in options else options[0]
			return default if default in options else options[0]

		def select_boolean(title, default=False):
			if not bool_queue:
				return default
			return bool_queue.pop(0)

		prompt_answers = {
			"session name": session or "",
			"image path": ",".join(image) if image else "",
			"attach file path": ",".join(attach) if attach else "",
			"mcp server command": mcp or "",
		}

		def prompt_ask(prompt, default=""):
			lowered = str(prompt).lower()
			for key, value in prompt_answers.items():
				if key in lowered:
					return value
			return default

		ui._select_option = select_option
		ui._select_boolean = select_boolean
		ui.select_model = MagicMock(return_value=model)
		ui.select_free_model = MagicMock(return_value=model)
		return patch("libs.terminal_ui.Prompt.ask", side_effect=prompt_ask)

	def test_launch_preserves_and_sets_agentic_free_stream_search(self):
		ui = TerminalUI()
		args = _base_args(timeout=45, sandbox_backend="subprocess")
		with self._stub_launch_selectors(ui, output_format="plain"):
			with patch.object(ui.utility_manager, "clear_screen"):
				with patch.object(ui.console, "print"):
					result = ui.launch(args)

		self.assertTrue(result.tui)
		self.assertTrue(result.agentic)
		self.assertFalse(result.agent)
		self.assertFalse(result.gemini_style)
		self.assertTrue(result.free)
		self.assertEqual(result.mode, "code")
		self.assertEqual(result.model, "openrouter-free")
		self.assertTrue(result.stream)
		self.assertTrue(result.search)
		self.assertEqual(result.output_format, "plain")
		self.assertEqual(result.session, "my-session")
		self.assertTrue(result.history)
		self.assertEqual(result.timeout, 45)  # preserved from input args
		self.assertEqual(result.sandbox, "subprocess")
		self.assertEqual(result.sandbox_backend, "subprocess")

	def test_launch_markdown_output_disables_stream(self):
		ui = TerminalUI()
		args = _base_args()
		with self._stub_launch_selectors(ui, output_format="markdown", stream=True):
			with patch.object(ui.utility_manager, "clear_screen"):
				with patch.object(ui.console, "print"):
					result = ui.launch(args)
		self.assertEqual(result.output_format, "markdown")
		self.assertFalse(result.stream)

	def test_launch_gemini_style_workflow_sets_agentic_and_free(self):
		ui = TerminalUI()
		args = _base_args()
		with self._stub_launch_selectors(ui, workflow=WORKFLOW_GEMINI, free=False, output_format="plain"):
			with patch.object(ui.utility_manager, "clear_screen"):
				with patch.object(ui.console, "print"):
					result = ui.launch(args)

		self.assertTrue(result.gemini_style)
		self.assertTrue(result.agentic)
		self.assertTrue(result.free)
		self.assertTrue(result.stream)

	def test_launch_multi_agent_workflow(self):
		ui = TerminalUI()
		args = _base_args()
		with self._stub_launch_selectors(ui, workflow=WORKFLOW_AGENT, free=False):
			with patch.object(ui.utility_manager, "clear_screen"):
				with patch.object(ui.console, "print"):
					result = ui.launch(args)

		self.assertTrue(result.agent)
		self.assertFalse(result.agentic)
		self.assertFalse(result.gemini_style)

	def test_launch_generate_mode_and_docker_sandbox(self):
		ui = TerminalUI()
		args = _base_args()
		with self._stub_launch_selectors(
			ui, mode="generate", workflow=WORKFLOW_CLASSIC, free=False,
			sandbox="docker", safety="relaxed",
		):
			with patch.object(ui.utility_manager, "clear_screen"):
				with patch.object(ui.console, "print"):
					result = ui.launch(args)

		self.assertEqual(result.mode, "generate")
		self.assertEqual(result.sandbox, "docker")
		self.assertEqual(result.sandbox_backend, "docker")
		self.assertFalse(result.unsafe)
		self.assertEqual(result.safety, "relaxed")

	def test_launch_no_sandbox_sets_unsafe(self):
		ui = TerminalUI()
		args = _base_args()
		with self._stub_launch_selectors(
			ui, workflow=WORKFLOW_CLASSIC, free=False, sandbox="off",
		):
			with patch.object(ui.utility_manager, "clear_screen"):
				with patch.object(ui.console, "print"):
					result = ui.launch(args)

		self.assertEqual(result.sandbox, "off")
		self.assertEqual(result.sandbox_backend, "none")
		self.assertTrue(result.unsafe)

	def test_launch_advanced_image_attach_yolo(self):
		ui = TerminalUI()
		args = _base_args()
		with self._stub_launch_selectors(
			ui, workflow=WORKFLOW_CLASSIC, free=False, configure_more=True,
			yolo=True, yes=True, science=True, interactive_charts=True,
			image=["shot.png"], attach=["data.csv"], mcp="npx -y server",
			session="",
		):
			with patch.object(ui.utility_manager, "clear_screen"):
				with patch.object(ui.console, "print"):
					result = ui.launch(args)

		self.assertTrue(result.yolo)
		self.assertTrue(result.yes)
		self.assertTrue(result.science)
		self.assertTrue(result.interactive_charts)
		self.assertEqual(result.image, ["shot.png"])
		self.assertEqual(result.attach, ["data.csv"])
		self.assertEqual(result.mcp_server, ["npx", "-y", "server"])
		self.assertIsNone(result.session)


class TestTerminalUIInteractiveSettings(unittest.TestCase):
	def test_interactive_settings_includes_new_keys(self):
		ui = TerminalUI()
		interp = MagicMock()
		interp.INTERPRETER_MODE = "code"
		interp.INTERPRETER_MODEL_LABEL = "gpt-4o"
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.INTERPRETER_LANGUAGE = "python"
		interp.DISPLAY_CODE = False
		interp.EXECUTE_CODE = False
		interp.SAVE_CODE = False
		interp.INTERPRETER_HISTORY = False
		interp.args = _base_args(agentic=False, agent=False, free=False, stream=True)

		option_returns = iter([
			"project",  # mode
			WORKFLOW_AGENTIC,  # workflow
			"python",  # language
			"docker",  # sandbox
			"strict",  # safety
			"json",  # output format
		])

		def select_option(title, options, default, help_text=None):
			return next(option_returns)

		# mode=project asks: free, display, history, stream, search (no exec/save)
		bools = iter([True, True, True, True, False])

		with patch.object(ui, "_select_option", side_effect=select_option):
			with patch.object(ui, "_select_boolean", side_effect=lambda *a, **k: next(bools)):
				with patch.object(ui, "select_free_model", return_value="groq-llama"):
					settings = ui.interactive_settings(interp)

		self.assertEqual(settings["mode"], "project")
		self.assertEqual(settings["workflow"], WORKFLOW_AGENTIC)
		self.assertTrue(settings["agentic"])
		self.assertTrue(settings["free"])
		self.assertEqual(settings["model"], "groq-llama")
		self.assertEqual(settings["sandbox"], "docker")
		self.assertEqual(settings["safety"], "strict")
		self.assertEqual(settings["output_format"], "json")
		self.assertTrue(settings["stream"])


class TestApplyRuntimeSettingsParity(unittest.TestCase):
	def test_apply_runtime_settings_wires_agentic_sandbox_stream(self):
		from libs.core.session import apply_runtime_settings

		interp = MagicMock()
		interp.args = _base_args()
		interp.INTERPRETER_MODE = "code"
		interp._apply_mode = MagicMock()

		settings = {
			"mode": "chat",
			"agentic": True,
			"agent": False,
			"gemini_style": False,
			"free": True,
			"stream": False,
			"search": True,
			"sandbox": "off",
			"safety": "off",
			"output_format": "plain",
			"yolo": True,
			"yes": True,
			"science": True,
			"interactive_charts": True,
		}
		apply_runtime_settings(
			interp, settings, display_fn=MagicMock(), model_exists_fn=lambda p: True,
		)

		interp._apply_mode.assert_called_with("chat")
		self.assertTrue(interp.args.agentic)
		self.assertFalse(interp.args.agent)
		self.assertTrue(interp.args.free)
		self.assertFalse(interp.args.stream)
		self.assertTrue(interp.args.search)
		self.assertEqual(interp.args.sandbox, "off")
		self.assertTrue(interp.args.unsafe)
		self.assertEqual(interp.args.sandbox_backend, "none")
		self.assertEqual(interp.args.safety, "off")
		self.assertEqual(interp.args.output_format, "plain")
		self.assertTrue(interp.args.yolo)
		self.assertTrue(interp.AUTO_YES)
		self.assertTrue(interp.UNSAFE_EXECUTION)


if __name__ == "__main__":
	unittest.main()
