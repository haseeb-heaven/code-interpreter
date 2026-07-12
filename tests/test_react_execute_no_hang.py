"""Regression tests for the --agentic execute hang (plt.show() + --yes).

Bug: ``python interpreter.py --agentic --yes -m <model>`` with a task that
generates matplotlib code ending in ``plt.show()`` hung indefinitely at the
"Execute the code? Y/N" / "Executing execute..." step, even with ``--yes``.

Root causes fixed:
1. The ReAct executor never honoured ``--yes``/``auto_yes`` — it always fell
   through to ``CodeInterpreter``'s own blocking ``input()`` prompt.
2. Chart-generation code (``plt.show()``) was never routed through the
   auto-save / non-interactive-backend hook that the CLI (``--cli``) path
   already uses, so a GUI backend could block forever waiting on an event
   loop that never resolves inside the sandbox.

These tests simulate a real blocking terminal (``input()`` that never
returns) and assert the ReAct execute path completes promptly regardless,
plus a real (non-mocked) sandbox run proving ``plt.show()`` no longer hangs.
"""
from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from libs.agent.actions.executor import ExecutorAction

HANG_TIMEOUT_SECONDS = 5


def _blocking_input(prompt: str = "") -> str:
    """Simulate a real terminal stuck waiting for a keypress that never comes."""
    time.sleep(9999)
    return "y"  # pragma: no cover - unreachable, kept for clarity


class TestExecuteNeverBlocksOnStdin(unittest.TestCase):
    """Root cause #1: --yes must fully bypass any input()-based confirmation.

    Uses the *real* ``CodeInterpreter`` (not a mock) so that, pre-fix, the
    executor genuinely reaches ``CodeInterpreter._safe_input`` -> blocking
    ``input()``. A mocked ``code_interpreter`` would hide this bug entirely
    since the mock never calls the real (blocking) implementation.
    """

    def _run_with_blocked_stdin(self, executor: ExecutorAction, code: str):
        result_holder: dict = {}

        def target():
            with patch("builtins.input", side_effect=_blocking_input):
                result_holder["result"] = executor.run(code=code, language="python")

        thread = threading.Thread(target=target, daemon=True)
        start = time.time()
        thread.start()
        thread.join(timeout=HANG_TIMEOUT_SECONDS)
        elapsed = time.time() - start
        return thread, elapsed, result_holder

    def test_execute_action_completes_even_if_stdin_would_block_forever(self):
        from libs.code_interpreter import CodeInterpreter
        from libs.safety_manager import ExecutionSafetyManager

        safety = ExecutionSafetyManager()
        code_interpreter = CodeInterpreter(safety_manager=safety)
        executor = ExecutorAction(code_interpreter=code_interpreter, safety_manager=safety)

        thread, elapsed, result_holder = self._run_with_blocked_stdin(executor, "print(42)")

        self.assertFalse(
            thread.is_alive(),
            "execute action is still blocked on stdin — the --yes hang regressed",
        )
        self.assertLess(elapsed, HANG_TIMEOUT_SECONDS)
        self.assertIn("result", result_holder)
        self.assertFalse(result_holder["result"].has_error)
        self.assertIn("42", result_holder["result"].output)


class TestChartExecutionNeverHangs(unittest.TestCase):
    """Root cause #2: plt.show() must never rely on a live GUI event loop."""

    def test_plt_show_code_executes_and_returns_promptly(self):
        """End-to-end (real CodeInterpreter, real subprocess): a plt.show()
        script must complete well within the sandbox timeout, not hang."""
        from libs.code_interpreter import CodeInterpreter
        from libs.safety_manager import ExecutionSafetyManager

        safety = ExecutionSafetyManager()
        code_interpreter = CodeInterpreter(safety_manager=safety)
        executor = ExecutorAction(code_interpreter=code_interpreter, safety_manager=safety)

        code = (
            "import matplotlib.pyplot as plt\n"
            "plt.plot([1, 2, 3])\n"
            "plt.show()\n"
            "print('done')\n"
        )

        start = time.time()
        result = executor.run(code=code, language="python")
        elapsed = time.time() - start

        self.assertLess(
            elapsed,
            20,
            f"plt.show() execution took {elapsed:.1f}s — likely blocked on a GUI event loop",
        )
        self.assertFalse(result.has_error, f"Unexpected error: {result.error}")
        self.assertIn("done", result.output)


if __name__ == "__main__":
    unittest.main()
