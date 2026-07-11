"""JSONL trajectory logger for ReAct agent runs."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any


_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[=:]\s*([^\s,;]+)"
)


def redact(text: str) -> str:
    """Redact obvious secret assignments from log text."""
    if not text:
        return text
    return _SECRET_RE.sub(r"\1=[REDACTED]", str(text))


class TrajectoryLogger:
    """Append structured ReAct steps to a JSONL file."""

    def __init__(self, path: str, run_id: str):
        self.path = path
        self.run_id = run_id
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _write(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload["run_id"] = self.run_id
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        for key in ("thought", "action_input", "observation", "failure_reason", "summary"):
            if key in payload and isinstance(payload[key], str):
                payload[key] = redact(payload[key])
            elif key in payload and isinstance(payload[key], dict):
                payload[key] = json.loads(redact(json.dumps(payload[key])))
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def log_step(
        self,
        step: int,
        thought: str,
        action: str,
        action_input: Any,
        observation: str,
        tokens: int = 0,
        cost: float = 0.0,
        status: str = "running",
    ) -> None:
        self._write(
            {
                "type": "step",
                "step": step,
                "thought": thought,
                "action": action,
                "action_input": action_input,
                "observation": observation,
                "tokens": tokens,
                "cost": cost,
                "status": status,
            }
        )

    def log_summary(
        self,
        status: str,
        steps: int,
        total_tokens: int = 0,
        total_cost: float = 0.0,
        failure_reason: str = "",
        summary: str = "",
    ) -> None:
        self._write(
            {
                "type": "summary",
                "status": status,
                "steps": steps,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
                "failure_reason": failure_reason,
                "summary": summary,
            }
        )
