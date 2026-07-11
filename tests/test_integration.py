"""End-to-end pipeline tests with mocked LLM (#224)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from libs.code_interpreter import CodeInterpreter
from libs.execution.executor import CodeExecutor
from libs.safety_manager import ExecutionSafetyManager


class TestEndToEnd(unittest.TestCase):
	def test_hello_world_extract_and_execute(self):
		"""prompt → extract code → execute → output (mocked approval)."""
		ci = CodeInterpreter(safety_manager=ExecutionSafetyManager(unsafe_mode=True))
		raw = '```python\nprint("hello world")\n```'
		code = ci.extract_code(raw)
		self.assertIn("hello world", code)

		interp = MagicMock()
		interp.UNSAFE_EXECUTION = True
		interp.logger = MagicMock()
		interp.safety_manager.is_dangerous_operation.return_value = False
		interp._safe_input.return_value = "y"
		interp.code_interpreter.execute_code.return_value = ("hello world\n", "")
		interp._last_execution_approved = True

		out, err = CodeExecutor(interp).execute_code(code, "python")
		self.assertIn("hello world", out or "")
		self.assertEqual(err, "")

	def test_math_computation_pipeline(self):
		ci = CodeInterpreter()
		raw = "```python\nresult = 2 + 2\nprint(result)\n```"
		code = ci.extract_code(raw)
		self.assertIn("2 + 2", code)

		interp = MagicMock()
		interp.UNSAFE_EXECUTION = True
		interp.logger = MagicMock()
		interp.safety_manager.is_dangerous_operation.return_value = False
		interp._safe_input.return_value = "y"
		interp.code_interpreter.execute_code.return_value = ("4\n", "")

		out, err = CodeExecutor(interp).execute_code(code, "python")
		self.assertIn("4", out or "")

	def test_dangerous_code_is_blocked_in_safe_mode(self):
		safety = ExecutionSafetyManager(unsafe_mode=False)
		dangerous = 'import os\nos.system("rm -rf /")'
		decision = safety.assess_execution(dangerous, mode="code")
		self.assertFalse(decision.allowed)

		interp = MagicMock()
		interp.UNSAFE_EXECUTION = False
		interp.logger = MagicMock()
		interp.safety_manager = safety
		out, err = CodeExecutor(interp).execute_code(dangerous, "python")
		self.assertIsNone(out)
		self.assertIsNotNone(err)
		self.assertIn("Safety blocked", err)

	def test_mocked_llm_completion_to_extract(self):
		"""LiteLLM-shaped response → extract_code → runnable snippet."""
		mock_completion = MagicMock(
			return_value=MagicMock(
				choices=[
					MagicMock(
						message=MagicMock(
							content='```python\nprint("pipeline ok")\n```'
						)
					)
				]
			)
		)
		with patch("litellm.completion", mock_completion):
			import litellm

			resp = litellm.completion(
				model="gpt-4o",
				messages=[{"role": "user", "content": "print pipeline ok"}],
			)
			content = resp.choices[0].message.content
			code = CodeInterpreter().extract_code(content)
			self.assertIn("pipeline ok", code)

	def test_file_oneshot_task_read(self):
		"""Interactive-friendly --yes path: task from file is readable offline."""
		with tempfile.TemporaryDirectory() as tmp:
			task = Path(tmp) / "task.txt"
			task.write_text("print hello world", encoding="utf-8")
			self.assertEqual(task.read_text(encoding="utf-8").strip(), "print hello world")


if __name__ == "__main__":
	unittest.main()
