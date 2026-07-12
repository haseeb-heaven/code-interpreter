"""Integration: main_loop slash commands for /tools and /memory (mocked REPL)."""

from __future__ import annotations

import io
import unittest
from unittest.mock import MagicMock, patch

from libs.core.main_loop import run_interpreter_main
from libs.memory.context_manager import ContextWindowManager
from libs.tools.bootstrap import build_registry


def _base_interp(**overrides):
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
	interp.INTERPRETER_HISTORY = False
	interp.DISPLAY_CODE = False
	interp.SAVE_CODE = False
	interp.EXECUTE_CODE = False
	interp.config_values = {"start_sep": "```", "end_sep": "```"}
	interp.history = []
	interp.logger = MagicMock()
	interp.console = MagicMock()
	interp.utility_manager = MagicMock()
	interp.utility_manager.get_os_platform.return_value = ("Windows", "10")
	interp.utility_manager.extract_file_name.return_value = None
	interp.history_manager = MagicMock()
	interp.package_manager = MagicMock()
	interp.safety_manager = MagicMock()
	interp._structured_output_active.return_value = False
	interp._display_session_banner = MagicMock()
	interp._is_recoverable_runtime_error.return_value = False
	interp.session_store = None
	interp.conversation_history = []
	interp.output_formatter = None
	interp.tool_registry = build_registry(MagicMock(), MagicMock())
	interp.memory = ContextWindowManager(max_tokens=8000, history_file="history/history.json")
	for key, value in overrides.items():
		setattr(interp, key, value)
	return interp


class TestMainLoopToolsSlashIntegration(unittest.TestCase):
	def test_tools_list_prints_registered_names(self):
		interp = _base_interp()
		interp._safe_input.side_effect = ["/tools list", "/exit"]

		buf = io.StringIO()
		with patch("libs.interpreter_lib.display_markdown_message"), \
		     patch("libs.interpreter_lib.display_code"), \
		     patch("sys.stdout", buf):
			run_interpreter_main(interp, "3.4.0")

		out = buf.getvalue()
		self.assertIn("Available tools:", out)
		self.assertIn("execute_code", out)
		self.assertIn("read_file", out)


class TestMainLoopMemorySlashIntegration(unittest.TestCase):
	def test_memory_stats_and_clear(self):
		import tempfile
		from pathlib import Path

		with tempfile.TemporaryDirectory() as tmp:
			hist = str(Path(tmp) / "history.json")
			interp = _base_interp()
			interp.memory = ContextWindowManager(max_tokens=8000, history_file=hist)
			interp.memory.add({"task": "prior", "content": "remember this fact", "role": "user"})
			interp._safe_input.side_effect = ["/memory stats", "/memory clear", "/memory show", "/exit"]

			messages = []

			def _capture(msg):
				messages.append(str(msg))

			with patch("libs.interpreter_lib.display_markdown_message", side_effect=_capture), \
			     patch("libs.interpreter_lib.display_code"):
				run_interpreter_main(interp, "3.4.0")

			joined = "\n".join(messages)
			self.assertIn("Memory stats:", joined)
			self.assertIn("Memory cleared.", joined)
			self.assertIn("Memory is empty.", joined)


class TestAgentModeMainRouting(unittest.TestCase):
	def test_agent_without_agentic_uses_interpreter_main(self):
		from interpreter import main

		with patch("interpreter.Interpreter") as mock_cls, \
		     patch("interpreter.prepare_args", side_effect=lambda a, _argv: a), \
		     patch("interpreter.maybe_show_first_run_welcome"), \
		     patch("interpreter._handle_session_mgmt_flags", return_value=False):
			inst = mock_cls.return_value
			main(
				[
					"interpreter.py",
					"--agent",
					"--cli",
					"-m",
					"gpt-4o",
					"--mode",
					"code",
					"-f",
					"task.txt",
				]
			)
			inst.interpreter_main.assert_called_once()
			inst.interpreter_agentic_main.assert_not_called()
			inst.interpreter_auto_main.assert_not_called()


if __name__ == "__main__":
	unittest.main()
