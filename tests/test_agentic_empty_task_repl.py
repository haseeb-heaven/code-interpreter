"""Empty-task / --yes / EOF handling for agentic and autonomous REPLs.

Regression: ``--agentic --yes`` without ``-f`` used to spam
``Task cannot be empty.`` forever because ``_safe_input(..., default="")``
returns immediately under AUTO_YES.
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
	def test_yes_without_file_exits_2_once_no_spam(self):
		"""--yes without -f must exit 2 with usage; never loop on empty task."""
		from libs.interpreter_lib import Interpreter

		interp, printed = _make_agentic_interp(auto_yes=True, file=None, prompt_file=False)
		# If the bug returns, this would spin forever on empty defaults.
		call_count = {"n": 0}

		def evil_safe_input(prompt, default=""):
			call_count["n"] += 1
			if call_count["n"] > 5:
				raise AssertionError("infinite empty-task loop under --yes")
			# Simulate pre-fix AUTO_YES behavior
			return default if default is not None else ""

		interp._safe_input = evil_safe_input

		with patch("libs.agent.react_controller.ReActController"):
			with self.assertRaises(SystemExit) as cm:
				Interpreter.interpreter_agentic_main(interp)

		self.assertEqual(cm.exception.code, 2)
		joined = "\n".join(printed).lower()
		self.assertTrue(
			"-f" in joined or "--file" in joined or "file" in joined,
			f"expected usage mentioning -f/--file, got: {printed}",
		)
		empty_msgs = [p for p in printed if "Task cannot be empty" in p]
		self.assertLessEqual(len(empty_msgs), 1)

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

	def test_cli_agentic_yes_without_file_exits_2(self):
		"""End-to-end: --agentic --yes without -f must exit 2 (not spam / exit 0)."""
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
				"-m",
				"openrouter-free",
			],
			cwd=str(root),
			capture_output=True,
			text=True,
			timeout=60,
		)
		self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
		combined = (proc.stdout + proc.stderr).lower()
		self.assertTrue("-f" in combined or "--file" in combined or "file" in combined)
		self.assertLessEqual(combined.count("task cannot be empty"), 1)



class AutoEmptyTaskReplTests(unittest.TestCase):
	def test_yes_without_file_exits_2_once_no_spam(self):
		from libs.interpreter_lib import Interpreter

		interp, printed = _make_agentic_interp(auto_yes=True, file=None, prompt_file=False)
		interp.args.yolo = True
		call_count = {"n": 0}

		def evil_safe_input(prompt, default=""):
			call_count["n"] += 1
			if call_count["n"] > 5:
				raise AssertionError("infinite empty-task loop under --yes")
			return default if default is not None else ""

		interp._safe_input = evil_safe_input

		with patch("libs.agent.auto_loop.AutonomousAgentLoop"):
			with patch("libs.tools.bootstrap.build_native_fs_registry") as reg:
				reg.return_value = MagicMock()
				with patch("libs.memory.ContextManager"):
					with self.assertRaises(SystemExit) as cm:
						Interpreter.interpreter_auto_main(interp)

		self.assertEqual(cm.exception.code, 2)
		empty_msgs = [p for p in printed if "Task cannot be empty" in p]
		self.assertLessEqual(len(empty_msgs), 1)


if __name__ == "__main__":
	unittest.main()
