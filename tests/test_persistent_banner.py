# -*- coding: utf-8 -*-
"""Coverage for the persistent INTERPRETER banner (generalized beyond --gemini-style).

Verifies that the banner shows at every genuinely-interactive entry point
(--cli classic REPL, --agentic, --gemini-style, the autonomous --yolo loop)
but NOT for one-shot ``-f`` / structured-output runs, and that the existing
``/clear`` clear-screen mechanism redraws the banner immediately after
clearing (``UtilityManager.clear_screen``).
"""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from libs.core.main_loop import run_interpreter_main
from libs.utility_manager import UtilityManager
from tests.interactive.helpers import make_interp


def _make_agentic_interp(*, gemini_style=False, auto_yes=False, file=None, prompt_file=False, inputs=None):
	"""Mirrors tests/test_agentic_empty_task_repl.py's fixture for interpreter_agentic_main /
	interpreter_auto_main coverage."""
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
		file=file,
		agent=False,
		agentic=True,
		gemini_style=gemini_style,
		free=False,
		cli=True,
		tui=False,
		yolo=False,
		mcp_server=None,
		search=False,
	)
	with patch.object(Interpreter, "__init__", lambda self, a: None):
		interp = Interpreter(args)
		interp.args = args
		interp.AUTO_YES = auto_yes
		interp.INTERPRETER_MODEL = "local-model"
		interp.INTERPRETER_MODEL_LABEL = "local-model"
		interp.INTERPRETER_PROMPT_FILE = prompt_file
		interp.UNSAFE_EXECUTION = False
		interp.MAX_REPAIR_ATTEMPTS = 3
		interp.config_values = {"model": "local-model"}
		interp.terminal_ui = None
		interp.logger = MagicMock()
		interp.console = MagicMock()
		interp._structured_output_active = lambda: False
		if inputs is not None:
			it = iter(inputs)

			def _next(prompt, default=None):
				try:
					return next(it)
				except StopIteration:
					return None

			interp._safe_input = _next
		return interp


class TestAgenticEntryPointShowsBanner(unittest.TestCase):
	"""``--agentic`` (with or without --gemini-style) is a genuinely interactive
	REPL, so it must render the persistent INTERPRETER banner at start."""

	def test_plain_agentic_repl_shows_banner(self):
		interp = _make_agentic_interp(gemini_style=False, inputs=["/exit"])
		with patch("libs.agent.gemini_ui.render_persistent_banner") as mock_banner:
			with patch("libs.agent.react_controller.ReActController"):
				from libs.interpreter_lib import Interpreter

				Interpreter.interpreter_agentic_main(interp)
		mock_banner.assert_called_once_with(interp.console)

	def test_gemini_style_repl_shows_full_startup_screen_not_double_banner(self):
		"""--gemini-style keeps using render_startup_screen (banner+tips) and must
		NOT also fire the plain render_persistent_banner (no duplicate banner)."""
		interp = _make_agentic_interp(gemini_style=True, inputs=["/exit"])
		with patch("libs.agent.gemini_ui.render_startup_screen") as mock_startup, patch(
			"libs.agent.gemini_ui.render_persistent_banner"
		) as mock_persistent:
			with patch("libs.agent.react_controller.ReActController"):
				from libs.interpreter_lib import Interpreter

				Interpreter.interpreter_agentic_main(interp)
		mock_startup.assert_called_once_with(interp.console)
		mock_persistent.assert_not_called()

	def test_one_shot_file_agentic_run_does_not_show_banner(self):
		"""A `-f` prompt-file run is one-shot (AGENTS.md) — no banner noise."""
		import tempfile

		with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
			fh.write("print('hi')")
			path = fh.name

		interp = _make_agentic_interp(gemini_style=False, prompt_file=True, file=path)
		interp.args.file = path
		with patch("libs.agent.gemini_ui.render_persistent_banner") as mock_banner:
			with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
				mock_ctrl.return_value.run.return_value = {}
				from libs.interpreter_lib import Interpreter

				Interpreter.interpreter_agentic_main(interp)
		mock_banner.assert_not_called()


class TestAutonomousLoopShowsBanner(unittest.TestCase):
	"""``--yolo`` / autonomous tool loop is also a human-facing interactive REPL."""

	def test_interactive_autonomous_loop_shows_banner(self):
		interp = _make_agentic_interp(inputs=["/exit"])
		interp.args.yolo = True
		with patch("libs.agent.gemini_ui.render_persistent_banner") as mock_banner:
			with patch("libs.agent.auto_loop.AutonomousAgentLoop"):
				with patch("libs.tools.bootstrap.build_native_fs_registry") as reg:
					reg.return_value = MagicMock()
					with patch("libs.memory.ContextManager"):
						from libs.interpreter_lib import Interpreter

						Interpreter.interpreter_auto_main(interp)
		mock_banner.assert_called_once_with(interp.console)

	def test_one_shot_file_autonomous_run_does_not_show_banner(self):
		import tempfile

		with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
			fh.write("list files")
			path = fh.name

		interp = _make_agentic_interp(prompt_file=True, file=path)
		interp.args.yolo = True
		interp.args.file = path
		with patch("libs.agent.gemini_ui.render_persistent_banner") as mock_banner:
			with patch("libs.agent.auto_loop.AutonomousAgentLoop") as mock_loop:
				mock_loop.return_value.run.return_value = "ok"
				with patch("libs.tools.bootstrap.build_native_fs_registry") as reg:
					reg.return_value = MagicMock()
					with patch("libs.memory.ContextManager"):
						from libs.interpreter_lib import Interpreter

						Interpreter.interpreter_auto_main(interp)
		mock_banner.assert_not_called()


class TestClassicCliEntryPointShowsBanner(unittest.TestCase):
	"""Classic ``--cli`` REPL (libs.core.main_loop.run_interpreter_main)."""

	def _run(self, commands, **overrides):
		interp = make_interp(**overrides)
		interp._safe_input.side_effect = list(commands) + ["/exit"]
		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.4.0")
		return interp

	def test_interactive_prompt_input_mode_shows_banner(self):
		with patch("libs.agent.gemini_ui.render_persistent_banner") as mock_banner:
			interp = self._run([], INTERPRETER_PROMPT_FILE=False)
		mock_banner.assert_called_once_with(interp.console)

	def test_prompt_file_one_shot_mode_does_not_show_banner(self):
		# AUTO_YES + a missing prompt file breaks out of the loop immediately
		# (no _safe_input needed) — enough to exercise the pre-loop banner gate.
		with patch("libs.agent.gemini_ui.render_persistent_banner") as mock_banner:
			self._run(
				[],
				INTERPRETER_PROMPT_FILE=True,
				INTERPRETER_PROMPT_INPUT=False,
				AUTO_YES=True,
			)
		mock_banner.assert_not_called()

	def test_structured_output_mode_does_not_show_banner(self):
		interp = make_interp(INTERPRETER_PROMPT_FILE=False)
		interp._structured_output_active.return_value = True
		interp._safe_input.side_effect = ["/exit"]
		with patch("libs.agent.gemini_ui.render_persistent_banner") as mock_banner, patch(
			"libs.interpreter_lib.display_markdown_message"
		), patch("libs.interpreter_lib.display_code"):
			run_interpreter_main(interp, "3.4.0")
		mock_banner.assert_not_called()


class TestClearScreenRedrawsBanner(unittest.TestCase):
	"""``UtilityManager.clear_screen`` is the one clear-screen mechanism in this
	REPL (``/clear``, prompt-mode switches, and the arrow-key TUI wizard's
	selector redraws all route through it) — a clear must immediately redraw
	the persistent banner so it visually "stays pinned" to the top."""

	def test_clear_screen_redraws_banner_by_default(self):
		um = UtilityManager()
		with patch("os.system") as mock_system, patch(
			"libs.agent.gemini_ui.render_persistent_banner"
		) as mock_banner:
			um.clear_screen()
		mock_system.assert_called_once()
		mock_banner.assert_called_once_with()

	def test_clear_screen_can_skip_banner_redraw(self):
		um = UtilityManager()
		with patch("os.system"), patch(
			"libs.agent.gemini_ui.render_persistent_banner"
		) as mock_banner:
			um.clear_screen(redraw_banner=False)
		mock_banner.assert_not_called()

	def test_clear_screen_banner_failure_is_swallowed(self):
		"""A banner render failure must never take down the (much more important)
		clear-screen call itself."""
		um = UtilityManager()
		with patch("os.system"), patch(
			"libs.agent.gemini_ui.render_persistent_banner", side_effect=RuntimeError("boom")
		):
			um.clear_screen()  # must not raise

	def test_repl_clear_command_invokes_clear_screen(self):
		"""End-to-end: the ``/clear`` REPL command calls clear_screen(), which in
		turn is responsible for the banner redraw (covered above)."""
		interp = make_interp()
		interp._safe_input.side_effect = ["/clear", "/exit"]
		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.4.0")
		interp.utility_manager.clear_screen.assert_called_once()


if __name__ == "__main__":
	unittest.main()
