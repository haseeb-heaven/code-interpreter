"""Executor action — run code inside the existing sandbox."""
from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Defense-in-depth: no single "execute" step should ever be able to hang the
# whole ReAct loop forever (an unforeseen blocking call beyond the
# confirmation prompt / plt.show() cases already handled below — e.g. a
# network stall or another blocking call in generated code). This is
# generous relative to the sandbox's own subprocess timeout (30s by default,
# see ExecutionSafetyManager.build_sandbox_context) so it never fires during
# normal, legitimate executions.
DEFAULT_EXECUTE_TIMEOUT_SECONDS = 90.0


@dataclass
class ExecutorResult:
    observation: str
    has_error: bool
    output: str
    error: str


class ExecutorAction:
    """Runs already-approved ReAct code through the sandbox.

    Confirmation (the "Execute the code? Y/N" prompt) is the *controller's*
    responsibility (see ``ReActController._authorize_execute``), which runs
    it outside any spinner and fully honours ``--yes``/``auto_yes``. By the
    time ``run()`` is called the action has already been authorized, so this
    class always calls ``execute_code(..., force_execute=True)`` — it must
    never fall back to ``CodeInterpreter``'s own blocking ``input()`` prompt,
    which is not ``--yes``-aware and previously caused the ReAct executor to
    hang indefinitely on stdin regardless of the ``--yes`` flag.

    As a safety net beyond that fix, ``execute_code`` itself is run on a
    daemon watchdog thread bounded by ``execute_timeout_seconds``: if any
    other unforeseen blocking call (e.g. a GUI event loop the chart hook
    didn't catch, or a network stall) prevents it from returning, the step
    fails loudly with a clear timeout message instead of hanging the CLI.
    """

    def __init__(
        self,
        code_interpreter: Any,
        safety_manager: Any,
        execute_timeout_seconds: float = DEFAULT_EXECUTE_TIMEOUT_SECONDS,
    ):
        self.code_interpreter = code_interpreter
        self.safety_manager = safety_manager
        self.execute_timeout_seconds = execute_timeout_seconds

    def run(self, code: str, language: str = "python") -> ExecutorResult:
        if not (code or "").strip():
            raise ValueError("No code available to execute")

        code = self._apply_chart_safety_hook(code)

        sandbox_context = None
        try:
            if hasattr(self.safety_manager, "build_sandbox_context"):
                sandbox_context = self.safety_manager.build_sandbox_context()
            output, error = self._execute_with_watchdog(code, language, sandbox_context)
            has_error = bool(error)
            if has_error:
                observation = f"ERROR: {error}\nOUTPUT: {output}"
            else:
                observation = f"SUCCESS OUTPUT: {output}"
            return ExecutorResult(
                observation=observation,
                has_error=has_error,
                output=output or "",
                error=error or "",
            )
        finally:
            if sandbox_context is not None and hasattr(self.safety_manager, "cleanup_sandbox_context"):
                try:
                    self.safety_manager.cleanup_sandbox_context(sandbox_context)
                except Exception:
                    pass

    def _execute_with_watchdog(self, code: str, language: str, sandbox_context: Any):
        """Run ``execute_code`` on a daemon watchdog thread with a hard deadline.

        Uses a plain ``daemon=True`` thread (not ``ThreadPoolExecutor``) so
        that if the underlying call truly never returns, the abandoned
        thread cannot block process exit via ``concurrent.futures``' atexit
        join.
        """
        result_queue: "queue.Queue" = queue.Queue(maxsize=1)

        def _worker():
            try:
                result_queue.put(
                    (
                        "ok",
                        self.code_interpreter.execute_code(
                            code,
                            language,
                            sandbox_context=sandbox_context,
                            force_execute=True,
                        ),
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive
                result_queue.put(("error", exc))

        thread = threading.Thread(target=_worker, daemon=True, name="react-execute-watchdog")
        thread.start()

        try:
            status, payload = result_queue.get(timeout=self.execute_timeout_seconds)
        except queue.Empty:
            logger.warning(
                "Execute action watchdog fired after %.1fs; abandoning the still-running "
                "execution thread instead of hanging the ReAct loop.",
                self.execute_timeout_seconds,
            )
            return (
                "",
                (
                    f"Execution timed out after {self.execute_timeout_seconds:.0f}s "
                    "(defense-in-depth watchdog). The step did not return in time; this "
                    "usually means a blocking call in the generated code (e.g. plt.show() "
                    "with a GUI backend, input(), or a network stall)."
                ),
            )

        if status == "error":
            raise payload
        return payload

    @staticmethod
    def _apply_chart_safety_hook(code: str) -> str:
        """Force a non-interactive matplotlib backend and redirect plt.show()
        to plt.savefig() before running in the sandbox (mirrors the hook the
        CLI/--cli path already applies via CodeExecutor.execute_generated_output).

        Without this, matplotlib code generated for "...and show" tasks can
        select a GUI backend (Tk/Qt) whose plt.show() blocks on an event loop
        that never resolves inside a headless sandbox subprocess.
        """
        try:
            from libs.output.chart_manager import inject_auto_save

            return inject_auto_save(code or "")
        except Exception:
            return code
