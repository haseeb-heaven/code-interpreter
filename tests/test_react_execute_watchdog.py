"""Regression tests for the ``ExecutorAction`` defense-in-depth watchdog.

Ported from ``fix/agentic-execute-hang`` (attempt 1) during the consolidation
of the three independent ``--agentic --yes`` execute-hang / tool-choice fix
branches. Attempt 2 (the base of this consolidated branch) fixed the actual
root causes -- the confirmation prompt colliding with the Rich spinner and
``--yes`` never reaching ``force_execute`` -- via
``ReActController._authorize_execute()`` running before the spinner starts.

This test covers the *additional* safety net attempt 1 introduced: even
after those root causes are fixed, no single "execute" step should be able
to hang the whole ReAct loop forever if some other unforeseen blocking call
occurs inside ``execute_code`` (e.g. a GUI event loop the chart hook didn't
catch, or a network stall). ``ExecutorAction`` runs ``execute_code`` on a
daemon watchdog thread bounded by ``execute_timeout_seconds`` and returns a
clear timeout observation instead of hanging.
"""
from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock

from libs.agent.actions.executor import ExecutorAction
from libs.agent.react_controller import ReActController

BOUND_SECONDS = 5.0


class TestExecutorActionWatchdog(unittest.TestCase):
    """Defense-in-depth: the execute step must never hang the whole process."""

    def test_hanging_execution_times_out_loudly(self):
        code_interpreter = MagicMock()

        def _hang(*_args, **_kwargs):
            time.sleep(30)  # much longer than the watchdog timeout below
            return "unreachable", ""  # pragma: no cover - unreachable

        code_interpreter.execute_code.side_effect = _hang
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()

        action = ExecutorAction(code_interpreter, safety, execute_timeout_seconds=0.3)

        start = time.time()
        result = action.run(code="print(1)", language="python")
        elapsed = time.time() - start

        self.assertLess(elapsed, BOUND_SECONDS, "watchdog did not return promptly")
        self.assertTrue(result.has_error)
        self.assertIn("timed out", result.observation.lower())

    def test_fast_execution_is_unaffected_by_watchdog(self):
        """The watchdog must be a no-op for normal, promptly-returning code."""
        code_interpreter = MagicMock()
        code_interpreter.execute_code.return_value = ("42\n", "")
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()

        action = ExecutorAction(code_interpreter, safety, execute_timeout_seconds=5.0)
        result = action.run(code="print(42)", language="python")

        self.assertFalse(result.has_error)
        self.assertIn("42", result.output)

    def test_default_timeout_is_generous_defense_in_depth(self):
        """Default watchdog window must stay well above the sandbox's own
        subprocess timeout so it never fires during legitimate executions."""
        from libs.agent.actions.executor import DEFAULT_EXECUTE_TIMEOUT_SECONDS

        self.assertGreaterEqual(DEFAULT_EXECUTE_TIMEOUT_SECONDS, 60.0)


class TestReActControllerThreadsExecuteTimeout(unittest.TestCase):
    """The controller must be able to configure the executor's watchdog."""

    def test_execute_timeout_seconds_is_passed_through_to_executor(self):
        code_interpreter = MagicMock()
        safety = MagicMock()

        controller = ReActController(
            model_name="gpt-4o",
            api_key="test",
            code_interpreter=code_interpreter,
            safety_manager=safety,
            log_path="logs/agent_react.jsonl",
            max_steps=5,
            execute_timeout_seconds=12.5,
        )

        self.assertEqual(controller.executor.execute_timeout_seconds, 12.5)

    def test_default_controller_uses_executor_default_timeout(self):
        from libs.agent.actions.executor import DEFAULT_EXECUTE_TIMEOUT_SECONDS

        code_interpreter = MagicMock()
        safety = MagicMock()

        controller = ReActController(
            model_name="gpt-4o",
            api_key="test",
            code_interpreter=code_interpreter,
            safety_manager=safety,
            log_path="logs/agent_react.jsonl",
            max_steps=5,
        )

        self.assertEqual(controller.executor.execute_timeout_seconds, DEFAULT_EXECUTE_TIMEOUT_SECONDS)


if __name__ == "__main__":
    unittest.main()
