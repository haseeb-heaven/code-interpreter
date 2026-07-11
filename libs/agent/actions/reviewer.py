"""Reviewer action — decide whether the task is solved."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, Optional

from libs.agent.llm import call_llm
from libs.agent.prompts import REVIEWER_SYSTEM


@dataclass
class ReviewerResult:
    observation: str
    passed: bool
    reason: str
    metrics: Dict[str, float] = field(default_factory=lambda: {"cost": 0.0, "tokens": 0})


class ReviewerAction:
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key

    def run(self, task: str, code: str, execution_result: str) -> ReviewerResult:
        prompt = (
            f"Task: {task}\n"
            f"Code:\n{code}\n"
            f"Execution result:\n{execution_result}\n"
        )
        content, metrics = call_llm(
            self.model_name,
            [
                {"role": "system", "content": REVIEWER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            self.api_key,
        )
        passed, reason = self._parse_review(content)
        observation = json.dumps({"passed": passed, "reason": reason})
        return ReviewerResult(
            observation=observation,
            passed=passed,
            reason=reason,
            metrics=metrics,
        )

    def _parse_review(self, content: str) -> tuple[bool, str]:
        text = (content or "").strip()
        # Prefer JSON object in the response
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                passed = bool(data.get("passed"))
                reason = str(data.get("reason", ""))
                return passed, reason
            except json.JSONDecodeError:
                pass
        upper = text.upper()
        if upper.startswith("YES"):
            return True, text
        if upper.startswith("NO"):
            return False, text
        return False, text or "Unable to parse review"
