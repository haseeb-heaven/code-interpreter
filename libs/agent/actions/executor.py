"""Executor action — run code inside the existing sandbox."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


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
    """

    def __init__(self, code_interpreter: Any, safety_manager: Any):
        self.code_interpreter = code_interpreter
        self.safety_manager = safety_manager

    def run(self, code: str, language: str = "python") -> ExecutorResult:
        if not (code or "").strip():
            raise ValueError("No code available to execute")

        code = self._apply_chart_safety_hook(code)

        sandbox_context = None
        try:
            if hasattr(self.safety_manager, "build_sandbox_context"):
                sandbox_context = self.safety_manager.build_sandbox_context()
            output, error = self.code_interpreter.execute_code(
                code,
                language,
                sandbox_context=sandbox_context,
                force_execute=True,
            )
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
