"""Integration tests for structured output + persistent sessions (#219 / #218)."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class TestHelpListsNewFlags(unittest.TestCase):
	def test_help_includes_output_format_and_session(self):
		proc = subprocess.run(
			[PYTHON, str(ROOT / "interpreter.py"), "--help"],
			cwd=str(ROOT),
			capture_output=True,
			text=True,
			timeout=60,
		)
		self.assertEqual(proc.returncode, 0, proc.stderr)
		out = proc.stdout + proc.stderr
		self.assertIn("--output-format", out)
		self.assertIn("--no-color", out)
		self.assertIn("--session", out)
		self.assertIn("--list-sessions", out)
		self.assertIn("--delete-session", out)
		self.assertIn("--new-session", out)


class TestSessionMgmtCliNoApiKeys(unittest.TestCase):
	def test_list_sessions_empty(self):
		with tempfile.TemporaryDirectory() as tmp:
			env = os.environ.copy()
			env["INTERPRETER_YES"] = "1"
			# Point session dir via monkeypatch in-process instead
			from interpreter import main
			from libs.memory.session_store import SessionStore

			with patch.object(SessionStore, "list_sessions", return_value=[]), \
				patch("sys.stdout", new_callable=io.StringIO) as buf:
				main(["interpreter.py", "--list-sessions"])
				self.assertIn("No saved sessions", buf.getvalue())

	def test_delete_missing_session(self):
		from interpreter import main
		from libs.memory.session_store import SessionStore

		with patch.object(SessionStore, "delete_session", return_value=False), \
			patch("sys.stdout", new_callable=io.StringIO) as buf:
			main(["interpreter.py", "--delete-session", "nope"])
			self.assertIn("not found", buf.getvalue())


class TestStructuredOutputMainLoopIntegration(unittest.TestCase):
	def test_code_mode_emits_json_after_turn(self):
		"""File + AUTO_YES + JSON formatter emits one JSON object and exits."""
		from libs.core.main_loop import run_interpreter_main
		from libs.output_formatter import OutputFormat, OutputFormatter

		with tempfile.TemporaryDirectory() as tmp:
			task_path = Path(tmp) / "task.txt"
			task_path.write_text("print hello", encoding="utf-8")

			buf = io.StringIO()
			formatter = OutputFormatter(fmt=OutputFormat.JSON, isatty=True)

			interp = MagicMock()
			interp.args = MagicMock(file=str(task_path))
			interp.INTERPRETER_PROMPT_FILE = True
			interp.INTERPRETER_PROMPT_INPUT = False
			interp.AUTO_YES = True
			interp.AGENT_MODE = False
			interp.SCRIPT_MODE = False
			interp.COMMAND_MODE = False
			interp.VISION_MODE = False
			interp.CHAT_MODE = False
			interp.CODE_MODE = True
			interp.INTERPRETER_MODE = "code"
			interp.INTERPRETER_LANGUAGE = "python"
			interp.INTERPRETER_MODEL = "local-model"
			interp.INTERPRETER_HISTORY = False
			interp.DISPLAY_CODE = False
			interp.SAVE_CODE = False
			interp.EXECUTE_CODE = True
			interp.config_values = {"start_sep": "```", "end_sep": "```"}
			interp.history = []
			interp.logger = MagicMock()
			interp.utility_manager = MagicMock()
			interp.utility_manager.get_os_platform.return_value = ("Windows", "10")
			interp.utility_manager.extract_file_name.return_value = None
			interp.utility_manager.read_file.return_value = "print hello"
			interp.output_formatter = formatter
			interp._structured_output_active.return_value = True
			interp.session_store = None
			interp.conversation_history = []
			interp._last_response_was_streamed = False
			interp._last_execution_approved = True

			llm_text = "```python\nprint('hello')\n```"
			interp.get_mode_prompt.return_value = "print hello"
			interp._generate_content_with_retries.return_value = llm_text
			interp.code_interpreter = MagicMock()
			interp.code_interpreter.extract_code.return_value = "print('hello')"
			interp._maybe_simplify_generated_code.side_effect = lambda t, c: c
			interp._execute_generated_output.return_value = ("hello\n", None, None)
			interp.history_manager = MagicMock()
			interp.package_manager = MagicMock()
			interp.safety_manager = MagicMock()

			real_emit = []

			def capture_emit(**kwargs):
				real_emit.append(kwargs)
				formatter.emit(**kwargs, file=buf)

			interp.emit_turn_result.side_effect = lambda **kw: capture_emit(**kw)
			interp.record_session_turn = MagicMock()

			run_interpreter_main(interp, "3.4.0")

			self.assertTrue(real_emit, "emit_turn_result was not called")
			payload = json.loads(buf.getvalue())
			self.assertEqual(payload["status"], "success")
			self.assertIn("print", payload.get("code", ""))
			self.assertIn("hello", payload.get("execution_output", ""))


class TestSessionResumeIntegration(unittest.TestCase):
	def test_bootstrap_loads_session_into_history(self):
		from libs.core import session as session_mod
		from libs.memory.session_store import SessionStore

		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			store = SessionStore("resume-me", session_dir=root)
			store.save(
				[{"assistant": {"task": "prior"}, "user": "prior", "system": {}}],
				model="local-model",
			)

			interp = MagicMock()
			interp.args = SimpleNamespace(
				lang="python",
				save_code=False,
				exec=False,
				display_code=False,
				model="local-model",
				mode="code",
				file=None,
				history=False,
				agent=False,
				yes=True,
				session="resume-me",
				output_format="plain",
				no_color=False,
				stream=True,
			)
			interp.logger = MagicMock()
			interp.utility_manager = MagicMock()
			interp.initialize_client = MagicMock()
			interp.initialize_mode = MagicMock()

			with patch.object(session_mod, "load_system_message", return_value="sys"), \
				patch("libs.memory.session_store.SESSION_DIR", root), \
				patch("sys.stdout", new_callable=io.StringIO) as buf:
				session_mod.bootstrap_interpreter(interp)

			self.assertIsNotNone(interp.session_store)
			self.assertEqual(len(interp.conversation_history), 1)
			self.assertTrue(interp.INTERPRETER_HISTORY)
			self.assertIn("Resumed session", buf.getvalue())


if __name__ == "__main__":
	unittest.main()
