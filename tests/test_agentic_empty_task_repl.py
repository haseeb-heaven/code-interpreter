"""Empty-task / --yes / EOF handling for agentic and autonomous REPLs.

Regression: ``--agentic --yes`` without ``-f`` used to either spam
``Task cannot be empty.`` forever (AUTO_YES short-circuit to ``""``) or
incorrectly require ``-f`` / exit 2. ``--yes`` only auto-approves Y/N;
without ``-f`` the interactive REPL must still wait for real task input.
"""
from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch


def _make_agentic_interp(*, auto_yes=False, file=None, prompt_file=False, inputs=None):
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
		gemini_style=False,
		free=False,
		cli=True,
		tui=False,
		yolo=False,
		mcp_server=None,
		search=False,
	)
	printed = []
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
		interp.logger = type(
			"L",
			(),
			{"error": lambda *a, **k: None, "info": lambda *a, **k: None},
		)()
		interp.console = type(
			"C",
			(),
			{"print": lambda self, *a, **k: printed.append(" ".join(str(x) for x in a))},
		)()
		if inputs is not None:
			it = iter(inputs)
			calls = {"n": 0}

			def _next(prompt, default=None):
				calls["n"] += 1
				if calls["n"] > 20:
					raise AssertionError("REPL input loop exceeded 20 calls (likely infinite)")
				try:
					return next(it)
				except StopIteration:
					return None

			interp._safe_input = _next
		return interp, printed


class AgenticEmptyTaskReplTests(unittest.TestCase):
	def test_yes_without_file_enters_repl_runs_task(self):
		"""--yes without -f must enter the REPL (no SystemExit 2) and run a task."""
		from libs.interpreter_lib import Interpreter

		interp, printed = _make_agentic_interp(
			auto_yes=True,
			file=None,
			prompt_file=False,
			inputs=["print hello", "/exit"],
		)
		with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
			mock_ctrl.return_value.run.return_value = "ok"
			Interpreter.interpreter_agentic_main(interp)

		mock_ctrl.return_value.run.assert_called_once_with("print hello")
		joined = "\n".join(printed).lower()
		self.assertNotIn("requires -f", joined)
		self.assertNotIn("requires --file", joined)
		self.assertIn("exiting", joined)
		empty_msgs = [p for p in printed if "Task cannot be empty" in p]
		self.assertEqual(len(empty_msgs), 0)

	def test_yes_does_not_short_circuit_task_prompt_to_empty(self):
		"""AUTO_YES must not return ``""`` for task entry (would spam empty-task)."""
		from libs.interpreter_lib import Interpreter

		interp = MagicMock()
		interp.AUTO_YES = True
		interp.logger = MagicMock()
		with patch("builtins.input", return_value="real task") as mock_input:
			result = Interpreter._safe_input(interp, "Enter your task: ", default="")
		self.assertEqual(result, "real task")
		mock_input.assert_called_once()

	def test_blank_lines_then_exit_no_infinite_loop(self):
		"""Blank Enter re-prompts; must not hang or spam unboundedly."""
		from libs.interpreter_lib import Interpreter

		interp, printed = _make_agentic_interp(
			auto_yes=False,
			inputs=["", "   ", "/exit"],
		)
		with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
			Interpreter.interpreter_agentic_main(interp)

		empty_msgs = [p for p in printed if "Task cannot be empty" in p]
		self.assertEqual(len(empty_msgs), 2)
		joined = "\n".join(printed).lower()
		self.assertIn("exiting", joined)
		mock_ctrl.return_value.run.assert_not_called()

	def test_eof_exits_cleanly_once(self):
		"""stdin EOF (None from _safe_input) exits the REPL once."""
		from libs.interpreter_lib import Interpreter

		interp, printed = _make_agentic_interp(auto_yes=False, inputs=[None])
		with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
			Interpreter.interpreter_agentic_main(interp)

		joined = "\n".join(printed).lower()
		self.assertIn("exiting", joined)
		empty_msgs = [p for p in printed if "Task cannot be empty" in p]
		self.assertEqual(len(empty_msgs), 0)
		mock_ctrl.return_value.run.assert_not_called()

	def test_safe_input_eof_returns_none_not_empty_default(self):
		"""EOF must not look like a submitted empty task when default is omitted."""
		from libs.interpreter_lib import Interpreter

		interp = MagicMock()
		interp.AUTO_YES = False
		interp.logger = MagicMock()
		with patch("builtins.input", side_effect=EOFError):
			result = Interpreter._safe_input(interp, "Enter your task: ")
		self.assertIsNone(result)

	def test_cli_agentic_yes_without_file_accepts_piped_exit(self):
		"""End-to-end: --agentic --yes without -f + piped /exit must not require -f."""
		import subprocess
		import sys
		from pathlib import Path

		root = Path(__file__).resolve().parents[1]
		proc = subprocess.run(
			[
				sys.executable,
				str(root / "interpreter.py"),
				"--agentic",
				"--yes",
				"--cli",
				"-m",
				"openrouter-free",
			],
			cwd=str(root),
			input="/exit\n",
			capture_output=True,
			text=True,
			timeout=60,
		)
		combined = (proc.stdout + proc.stderr).lower()
		self.assertNotIn("requires -f", combined)
		self.assertNotIn("--yes requires", combined)
		self.assertLessEqual(combined.count("task cannot be empty"), 1)
		# Soft-ok on live LLM/quota failures as long as REPL accepted input / exited.
		self.assertNotEqual(proc.returncode, 2, combined)


class AutoEmptyTaskReplTests(unittest.TestCase):
	def test_yes_without_file_enters_repl_runs_task(self):
		from libs.interpreter_lib import Interpreter

		interp, printed = _make_agentic_interp(
			auto_yes=True,
			file=None,
			prompt_file=False,
			inputs=["list files", "/exit"],
		)
		interp.args.yolo = True

		with patch("libs.agent.auto_loop.AutonomousAgentLoop") as mock_loop:
			mock_loop.return_value.run.return_value = "ok"
			with patch("libs.tools.bootstrap.build_native_fs_registry") as reg:
				reg.return_value = MagicMock()
				with patch("libs.memory.ContextManager"):
					Interpreter.interpreter_auto_main(interp)

		mock_loop.return_value.run.assert_called_once_with("list files")
		joined = "\n".join(printed).lower()
		self.assertNotIn("requires -f", joined)
		empty_msgs = [p for p in printed if "Task cannot be empty" in p]
		self.assertEqual(len(empty_msgs), 0)


if __name__ == "__main__":
	unittest.main()
