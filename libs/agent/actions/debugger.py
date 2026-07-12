"""Debugger action — diagnose failures for the next code step."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from libs.agent.llm import call_llm
from libs.agent.prompts import DEBUGGER_SYSTEM


@dataclass
class DebuggerResult:
    observation: str
    metrics: Dict[str, float] = field(default_factory=lambda: {"cost": 0.0, "tokens": 0})


class DebuggerAction:
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        on_fallback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.on_fallback = on_fallback

    def run(
        self,
        task: str,
        code: str,
        error: str = "",
        last_observation: str = "",
    ) -> DebuggerResult:
        prompt = (
            f"Task: {task}\n"
            f"Code:\n{code or '(none)'}\n"
            f"Error:\n{error or '(none)'}\n"
            f"Last observation:\n{last_observation or '(none)'}\n"
            "Provide root cause and concrete fix steps."
        )
        content, metrics = call_llm(
            self.model_name,
            [
                {"role": "system", "content": DEBUGGER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            self.api_key,
            on_fallback=self.on_fallback,
        )
        used = str(metrics.get("model_used") or "").strip()
        if used and used != self.model_name:
            self.model_name = used
        return DebuggerResult(observation=content.strip(), metrics=metrics)
