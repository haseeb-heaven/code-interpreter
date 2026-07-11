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
    def __init__(self, code_interpreter: Any, safety_manager: Any):
        self.code_interpreter = code_interpreter
        self.safety_manager = safety_manager

    def run(self, code: str, language: str = "python") -> ExecutorResult:
        if not (code or "").strip():
            raise ValueError("No code available to execute")

        sandbox_context = None
        try:
            if hasattr(self.safety_manager, "build_sandbox_context"):
                sandbox_context = self.safety_manager.build_sandbox_context()
            output, error = self.code_interpreter.execute_code(
                code,
                language,
                sandbox_context=sandbox_context,
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
