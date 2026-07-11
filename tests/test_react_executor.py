"""Unit tests for ReAct Executor action."""
import unittest
from unittest.mock import MagicMock

from libs.agent.actions.executor import ExecutorAction


class TestExecutorAction(unittest.TestCase):
    def test_success_observation(self):
        code_interpreter = MagicMock()
        code_interpreter.execute_code.return_value = ("42\n", "")
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()
        safety.cleanup_sandbox_context.return_value = None

        executor = ExecutorAction(code_interpreter=code_interpreter, safety_manager=safety)
        result = executor.run(code="print(42)", language="python")

        self.assertFalse(result.has_error)
        self.assertIn("42", result.observation)
        safety.cleanup_sandbox_context.assert_called_once()

    def test_error_observation(self):
        code_interpreter = MagicMock()
        code_interpreter.execute_code.return_value = ("", "NameError: x")
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()

        executor = ExecutorAction(code_interpreter=code_interpreter, safety_manager=safety)
        result = executor.run(code="print(x)", language="python")

        self.assertTrue(result.has_error)
        self.assertIn("NameError", result.observation)

    def test_missing_code_raises(self):
        executor = ExecutorAction(code_interpreter=MagicMock(), safety_manager=MagicMock())
        with self.assertRaises(ValueError):
            executor.run(code="", language="python")


if __name__ == "__main__":
    unittest.main()
