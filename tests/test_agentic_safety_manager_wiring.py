# -*- coding: utf-8 -*-
"""Regression test for issue #25 / #23: ``interpreter_agentic_main`` must build
its ``ReActController`` from the session's real ``code_interpreter``/
``safety_manager`` instead of letting ``ReActController`` construct
disconnected fresh ones (which always defaulted to ``SafetyLevel.STANDARD``,
silently ignoring ``--safety``/``--unsafe`` and any later ``/settings``
change made via ``ExecutionSafetyManager.set_safety_level``).
"""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from libs.interpreter_lib import Interpreter


def _make_agentic_interp(*, code_interpreter=None, safety_manager=None, inputs=None):
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
		gemini_style=False,
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
	interp.AUTO_YES = False
	interp.UNSAFE_EXECUTION = False
	interp.INTERPRETER_MODEL = "local-model"
	interp.INTERPRETER_MODEL_LABEL = "local-model"
	interp.INTERPRETER_PROMPT_FILE = False
	interp.MAX_REPAIR_ATTEMPTS = 3
	interp.config_values = {"model": "local-model"}
	interp.terminal_ui = None
	interp.logger = MagicMock()
	interp.console = MagicMock()
	interp._structured_output_active = lambda: False
	if code_interpreter is not None:
		interp.code_interpreter = code_interpreter
	if safety_manager is not None:
		interp.safety_manager = safety_manager
	it = iter(inputs if inputs is not None else ["/exit"])

	def _next(prompt, default=None):
		try:
			return next(it)
		except StopIteration:
			return None

	interp._safe_input = _next
	return interp


class TestAgenticControllerSharesSessionSafetyManager(unittest.TestCase):
	def test_make_controller_passes_session_code_interpreter_and_safety_manager(self):
		sentinel_code_interpreter = MagicMock(name="session_code_interpreter")
		sentinel_safety_manager = MagicMock(name="session_safety_manager")
		interp = _make_agentic_interp(
			code_interpreter=sentinel_code_interpreter,
			safety_manager=sentinel_safety_manager,
		)
		with patch("libs.agent.gemini_ui.render_persistent_banner"), patch(
			"libs.agent.react_controller.ReActController"
		) as mock_controller_cls:
			Interpreter.interpreter_agentic_main(interp)

		mock_controller_cls.assert_called_once()
		_, kwargs = mock_controller_cls.call_args
		self.assertIs(kwargs.get("code_interpreter"), sentinel_code_interpreter)
		self.assertIs(kwargs.get("safety_manager"), sentinel_safety_manager)

	def test_make_controller_tolerates_missing_attrs_on_bare_test_double(self):
		"""getattr fallback: test doubles that skip __init__ (and thus never set
		code_interpreter/safety_manager) must not crash the controller build."""
		interp = _make_agentic_interp()
		with patch("libs.agent.gemini_ui.render_persistent_banner"), patch(
			"libs.agent.react_controller.ReActController"
		) as mock_controller_cls:
			Interpreter.interpreter_agentic_main(interp)

		mock_controller_cls.assert_called_once()
		_, kwargs = mock_controller_cls.call_args
		self.assertIsNone(kwargs.get("code_interpreter"))
		self.assertIsNone(kwargs.get("safety_manager"))


if __name__ == "__main__":
	unittest.main()
