import os
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch

from libs.agents.base_agent import AgentContext
from libs.agents.executor_agent import ExecutorAgent
from libs.history_manager import History
from libs.interpreter_lib import Interpreter
from libs.memory.context_manager import ContextWindowManager
from libs.memory.memory_entry import MemoryEntry


class FakeLogger:
	def info(self, *args, **kwargs):
		pass

	def warning(self, *args, **kwargs):
		pass

	def error(self, *args, **kwargs):
		pass


class TestMemoryIntegration(unittest.TestCase):
	def _make_args(self):
		return Namespace(
			exec=False,
			save_code=False,
			mode="code",
			model="z-ai-glm-5",
			display_code=False,
			lang="python",
			file=None,
			history=False,
			upgrade=False,
			unsafe=False,
		)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_interpreter_wires_memory_manager_from_session_config(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args())

		self.assertIsInstance(interpreter.memory, ContextWindowManager)
		self.assertEqual(interpreter.memory.max_tokens, 8000)
		self.assertEqual(interpreter.memory.history_file, "history/history.json")
		self.assertEqual(interpreter.history_count, 3)

	def test_executor_adds_successful_runs_to_memory(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			history_file = os.path.join(temp_dir, "agent-memory.json")
			memory = ContextWindowManager(max_tokens=100, history_file=history_file)

			class FakeInterp:
				def __init__(self):
					self.memory = memory

			class FakeRouter:
				def __init__(self):
					self.interp = FakeInterp()

				def route(self, messages, config_values=None):
					return "```python\nprint('hello from memory')\n```"

			class FakeExecutor:
				def execute_generated_output(self, code, language, force_execute=False):
					return "hello from memory\n", None, None

			class FakePromptBuilder:
				def build(self, task, os_name):
					return f"Generate code for {task}"

			agent = ExecutorAgent(FakeRouter(), FakeExecutor(), FakePromptBuilder(), FakeLogger())
			context = agent.run(AgentContext(task="print hello from memory", os_name="Linux", language="python"))

			self.assertEqual(context.error, "")
			context_entries = memory.get_context("hello memory", limit=3)
			self.assertEqual(memory.stats()["entry_count"], 1)
			self.assertIn("hello from memory", context_entries[0]["content"])
			self.assertEqual(context_entries[0]["task"], "print hello from memory")

	def test_history_manager_can_read_memory_entry_schema(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			history_file = os.path.join(temp_dir, "history.json")
			memory = ContextWindowManager(max_tokens=100, history_file=history_file)
			memory.add(MemoryEntry(role="assistant", content="memory output", task="memory task", tokens=2))

			history = History(history_file)

			self.assertEqual(history.get_chat_history(1), [{"task": "memory task", "output": "memory output"}])
			self.assertEqual(history.get_code_history(1), [{"code": "memory output", "output": "memory output"}])

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("builtins.input", side_effect=["/memory stats", "/memory show", "/memory clear", "/exit"])
	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_memory_cli_commands_show_stats_and_clear(
		self, _mock_history, _mock_client, _mock_input, markdown_mock
	):
		with tempfile.TemporaryDirectory() as temp_dir:
			interpreter = Interpreter(self._make_args())
			interpreter.config_values = {"start_sep": "```", "end_sep": "```"}
			interpreter.memory = ContextWindowManager(max_tokens=100, history_file=os.path.join(temp_dir, "memory.json"))
			interpreter.memory.add(MemoryEntry(role="assistant", content="saved memory output", task="saved task", tokens=3))

			interpreter.interpreter_main("test-version")

			messages = [call.args[0] for call in markdown_mock.call_args_list if call.args]
			self.assertTrue(any("Memory stats:" in message for message in messages))
			self.assertTrue(any("saved memory output" in message for message in messages))
			self.assertTrue(any("Memory cleared." in message for message in messages))
			self.assertEqual(interpreter.memory.stats()["entry_count"], 0)


if __name__ == "__main__":
	unittest.main()
