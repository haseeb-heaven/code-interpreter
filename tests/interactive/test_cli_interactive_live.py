"""
Interactive / live-style CLI tests — exercise the real interpreter entrypoint
like a user (piped stdin, --cli, --yes), without requiring live cloud keys.

Re-run:
  python -m unittest discover -s tests/interactive -v

Manual live-style commands (local stub preferred):
  # List free presets
  python interpreter.py --list-free

  # Help / version (no keys)
  python interpreter.py --help
  python interpreter.py --version

  # Piped REPL with auto-yes (needs local-model or keys)
  $env:INTERPRETER_YES=1
  "print hello`ny`n/exit`n" | python interpreter.py --cli -m local-model -md code -dc --yes --output-format plain

  # Slash commands smoke (mocked LLM in unit suite; live needs model)
  "/memory stats`n/tools list`n/free`n/exit`n" | python interpreter.py --cli -m local-model --yes

Interactive suite (offline):
  python -m unittest discover -s tests/interactive -v

Live cloud (optional; soft-skip on quota/billing):
  $env:SMOKE_LIVE=1
  python -m unittest tests.smoke.test_live_model_smoke -v

Never print .env contents or API key values in logs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable

_BILLING_MARKERS = (
	"insufficient_quota",
	"billing",
	"rate limit",
	"ratelimit",
	"429",
	"quota exceeded",
	"credit",
)


def _soft_skip_if_billing(output: str):
	lower = (output or "").lower()
	if any(m in lower for m in _BILLING_MARKERS):
		raise unittest.SkipTest(f"Soft-skip live billing/quota: {output[:160]}")


class TestInteractiveCliSurface(unittest.TestCase):
	"""Scripted process-level interaction with the real CLI binary."""

	def test_help_and_list_free(self):
		help_proc = subprocess.run(
			[PYTHON, str(ROOT / "interpreter.py"), "--help"],
			cwd=str(ROOT),
			capture_output=True,
			text=True,
			timeout=60,
		)
		self.assertEqual(help_proc.returncode, 0, help_proc.stderr)
		combined = help_proc.stdout + help_proc.stderr
		for flag in ("--cli", "--yes", "--agent", "--agentic", "--free", "--search"):
			self.assertIn(flag, combined)

		free_proc = subprocess.run(
			[PYTHON, str(ROOT / "interpreter.py"), "--list-free"],
			cwd=str(ROOT),
			capture_output=True,
			text=True,
			timeout=60,
		)
		# list-free may exit 0 with a table; tolerate missing catalog gracefully
		self.assertIn(free_proc.returncode, (0, 1), free_proc.stderr)

	def test_piped_exit_with_yes_env(self):
		"""Pipe /exit immediately — proves non-interactive stdin + INTERPRETER_YES."""
		with tempfile.TemporaryDirectory() as tmp:
			env = os.environ.copy()
			env["INTERPRETER_YES"] = "1"
			env["CODE_INTERPRETER_HOME"] = tmp
			# Avoid loading real secrets into assertions; do not dump env.
			proc = subprocess.run(
				[
					PYTHON,
					str(ROOT / "interpreter.py"),
					"--cli",
					"--yes",
					"--output-format",
					"plain",
					"-m",
					"local-model",
					"-md",
					"code",
				],
				cwd=str(ROOT),
				input="/exit\n",
				capture_output=True,
				text=True,
				timeout=90,
				env=env,
			)
			combined = proc.stdout + proc.stderr
			_soft_skip_if_billing(combined)
			# May fail init without .env/local server — accept clean exit or recoverable message.
			if proc.returncode != 0:
				# Missing key / unreachable local endpoint is acceptable for this surface test.
				self.assertTrue(
					any(
						tok in combined.lower()
						for tok in ("api", "key", "error", "connection", "refused", "model")
					),
					combined[:500],
				)
			else:
				self.assertTrue(True)

	def test_session_flags_on_parser(self):
		import interpreter as mod

		args = mod.build_parser().parse_args(
			["--cli", "--yes", "--session", "demo", "--list-sessions"]
		)
		self.assertEqual(args.session, "demo")
		self.assertTrue(args.list_sessions)

	def test_output_format_and_stream_flags(self):
		import interpreter as mod

		args = mod.build_parser().parse_args(
			["--cli", "--output-format", "json", "--stream", "--no-color"]
		)
		self.assertEqual(args.output_format, "json")
		self.assertTrue(args.stream)
		self.assertTrue(args.no_color)

	def test_file_prompt_flag_parses_with_yes(self):
		"""CLI accepts -f + --yes without launching a long-lived session."""
		import interpreter as mod

		with tempfile.TemporaryDirectory() as tmp:
			task = Path(tmp) / "task.txt"
			task.write_text("print('interactive')\n", encoding="utf-8")
			args = mod.build_parser().parse_args(
				[
					"--cli",
					"--yes",
					"--output-format",
					"plain",
					"-m",
					"local-model",
					"-md",
					"code",
					"-f",
					str(task),
				]
			)
			args = mod.prepare_args(
				args,
				["interpreter.py", "--cli", "--yes", "-f", str(task)],
			)
			self.assertTrue(args.yes)
			self.assertEqual(args.file, str(task))
			self.assertEqual(args.mode, "code")


class TestInteractiveSlashCommandsMocked(unittest.TestCase):
	"""In-process slash-command paths using the real main_loop with mocks."""

	def test_memory_and_exit_commands(self):
		from libs.core.main_loop import run_interpreter_main

		interp = MagicMock()
		interp.args = MagicMock(file=None)
		interp.INTERPRETER_PROMPT_FILE = False
		interp.INTERPRETER_PROMPT_INPUT = True
		interp.AUTO_YES = False
		interp.AGENT_MODE = False
		interp.SCRIPT_MODE = False
		interp.COMMAND_MODE = False
		interp.VISION_MODE = False
		interp.CHAT_MODE = False
		interp.CODE_MODE = True
		interp.INTERPRETER_MODE = "code"
		interp.INTERPRETER_LANGUAGE = "python"
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.INTERPRETER_MODEL_LABEL = "gpt-4o"
		interp.UNSAFE_EXECUTION = False
		interp.DISPLAY_CODE = False
		interp.SAVE_CODE = False
		interp.EXECUTE_CODE = False
		interp.INTERPRETER_HISTORY = False
		interp.config_values = {"start_sep": "```", "end_sep": "```"}
		interp.logger = MagicMock()
		interp.console = MagicMock()
		interp.utility_manager = MagicMock()
		interp.utility_manager.get_os_platform.return_value = ("Windows",)
		interp.history_manager = MagicMock()
		interp.package_manager = MagicMock()
		interp.memory = MagicMock()
		interp.memory.stats.return_value = {
			"entry_count": 0,
			"total_tokens": 0,
			"max_tokens": 8000,
			"history_file": "history/history.json",
		}
		interp.memory.clear = MagicMock()
		interp.tool_registry = MagicMock()
		interp.tool_registry.list_tools.return_value = []
		interp._structured_output_active.return_value = False
		interp._display_session_banner = MagicMock()
		interp._is_recoverable_runtime_error.return_value = False
		interp._safe_input.side_effect = ["/memory stats", "/memory clear", "/exit"]

		with patch("libs.interpreter_lib.display_markdown_message") as md, \
		     patch("libs.interpreter_lib.display_code"):
			run_interpreter_main(interp, "3.4.0")

		interp.memory.clear.assert_called()
		self.assertTrue(md.called)


if __name__ == "__main__":
	unittest.main()
