"""Coder action — generate or update code for the ReAct agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from libs.agent.llm import call_llm
from libs.agent.prompts import CODER_SYSTEM
from libs.code_interpreter import CodeInterpreter


@dataclass
class CoderResult:
    observation: str
    code: str
    metrics: Dict[str, float] = field(default_factory=lambda: {"cost": 0.0, "tokens": 0})


class CoderAction:
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        code_interpreter: Optional[CodeInterpreter] = None,
        on_fallback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.code_interpreter = code_interpreter or CodeInterpreter()
        self.on_fallback = on_fallback

    def run(
        self,
        instruction: str,
        task: str,
        current_code: str = "",
        history: str = "",
    ) -> CoderResult:
        prompt = (
            f"Task: {task}\n"
            f"Instruction: {instruction}\n"
            f"Current code:\n{current_code or '(none)'}\n"
            f"History:\n{history or '(none)'}\n"
        )
        content, metrics = call_llm(
            self.model_name,
            [
                {"role": "system", "content": CODER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            self.api_key,
            on_fallback=self.on_fallback,
        )
        # Keep specialist model in sync if fallback happened without shared hook.
        used = str(metrics.get("model_used") or "").strip()
        if used and used != self.model_name:
            self.model_name = used
        code = self.code_interpreter.extract_code(content, "```python", "```")
        if not code or code == content:
            code = self.code_interpreter.extract_code(content, "```", "```")
        if not code:
            code = content.strip()
        return CoderResult(observation=code, code=code, metrics=metrics)
