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

    def test_unsupported_language_surfaces_clear_error(self):
        code_interpreter = MagicMock()
        code_interpreter.execute_code.side_effect = Exception(
            "Unsupported language: 'ruby' (normalized='ruby')"
        )
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()

        executor = ExecutorAction(code_interpreter=code_interpreter, safety_manager=safety)
        with self.assertRaises(Exception) as ctx:
            executor.run(code="puts 1", language="ruby")
        self.assertIn("ruby", str(ctx.exception))

    def test_execute_never_blocks_on_confirmation_prompt(self):
        """Regression: the ReAct executor must never rely on CodeInterpreter's
        own blocking Y/N prompt — the controller/--yes flow is responsible for
        any confirmation, so this action must always force_execute=True."""
        code_interpreter = MagicMock()
        code_interpreter.execute_code.return_value = ("42\n", "")
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()

        executor = ExecutorAction(code_interpreter=code_interpreter, safety_manager=safety)
        executor.run(code="print(42)", language="python")

        _, kwargs = code_interpreter.execute_code.call_args
        self.assertTrue(
            kwargs.get("force_execute"),
            "ExecutorAction must pass force_execute=True so it never blocks on stdin",
        )

    def test_matplotlib_show_is_intercepted_before_execution(self):
        """Regression: chart-generation code (plt.show()) must be routed through
        the same auto-save / non-interactive-backend hook used by the CLI path,
        so it can never hang waiting on a GUI event loop in the sandbox."""
        code_interpreter = MagicMock()
        code_interpreter.execute_code.return_value = ("Chart saved: chart.png\n", "")
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()

        executor = ExecutorAction(code_interpreter=code_interpreter, safety_manager=safety)
        code = "import matplotlib.pyplot as plt\nplt.plot([1, 2, 3])\nplt.show()\n"
        executor.run(code=code, language="python")

        executed_code = code_interpreter.execute_code.call_args.args[0]
        self.assertIn("matplotlib.use('Agg')", executed_code)
        self.assertIn("_ci_auto_show", executed_code)

    def test_non_chart_code_is_untouched(self):
        """The chart hook must be a no-op for code that never touches matplotlib."""
        code_interpreter = MagicMock()
        code_interpreter.execute_code.return_value = ("42\n", "")
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()

        executor = ExecutorAction(code_interpreter=code_interpreter, safety_manager=safety)
        executor.run(code="print(42)", language="python")

        executed_code = code_interpreter.execute_code.call_args.args[0]
        self.assertEqual(executed_code, "print(42)")


if __name__ == "__main__":
    unittest.main()
