"""Intent classification agent — runs BEFORE planning."""

from __future__ import annotations

import json
import re

from libs.agents.base_agent import AgentContext, BaseAgent

VALID_INTENTS = frozenset(
	{"code", "script", "command", "vision", "chat", "debug", "review", "test"}
)

INTENT_SYSTEM_PROMPT = """
You are an intent classifier for a code execution agent.
Given a user task, classify it into exactly one of these modes:
- code: generate and run Python/JS code
- script: generate a shell/bash script
- command: run a direct OS command
- vision: analyze an image
- chat: general question, no code needed
- debug: debug existing code provided by user
- review: review/critique existing code
- test: write tests for existing code

Return ONLY valid JSON: {"intent": "<mode>", "confidence": 0.0-1.0}
""".strip()


def _heuristic_intent(task: str) -> str:
	"""Fast fallback when the LLM response is not valid JSON."""
	lower = (task or "").lower()
	if any(w in lower for w in ("debug", "fix this", "traceback", "exception")):
		return "debug"
	if any(w in lower for w in ("review", "critique", "code review")):
		return "review"
	if any(w in lower for w in ("write test", "unit test", "pytest", "unittest")):
		return "test"
	if any(w in lower for w in ("image", "screenshot", "photo", "picture", "vision")):
		return "vision"
	if any(w in lower for w in ("bash script", "shell script", "write a script")):
		return "script"
	if lower.startswith(("run ", "execute ")) and "code" not in lower:
		return "command"
	if any(w in lower for w in ("what is", "explain", "why ", "how does", "tell me")):
		if not any(w in lower for w in ("print", "write code", "generate code", "compute", "calculate")):
			return "chat"
	return "code"


def _parse_intent_payload(text: str) -> dict:
	text = (text or "").strip()
	# Prefer a fenced JSON block if present.
	fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
	candidate = fence.group(1) if fence else text
	# Also accept a bare JSON object embedded in prose.
	if not candidate.lstrip().startswith("{"):
		match = re.search(r"\{[^{}]*\"intent\"[^{}]*\}", text, re.DOTALL)
		if match:
			candidate = match.group(0)
	return json.loads(candidate)


class IntentRouter(BaseAgent):
	def run(self, context: AgentContext) -> AgentContext:
		self._log(f"Classifying intent for: {context.task[:80]}")
		try:
			response = self.model_router.route(
				messages=[
					{"role": "system", "content": INTENT_SYSTEM_PROMPT},
					{"role": "user", "content": context.task},
				],
				config_values={"temperature": 0.0, "max_tokens": 64},
			)
			result = _parse_intent_payload(response)
			intent = str(result.get("intent", "code")).strip().lower()
			if intent not in VALID_INTENTS:
				intent = _heuristic_intent(context.task)
			context.intent = intent
			context.metadata["intent_confidence"] = float(result.get("confidence", 1.0))
			self._log(f"Intent: {context.intent} (confidence={context.metadata['intent_confidence']})")
		except Exception as exc:
			context.intent = _heuristic_intent(context.task)
			context.metadata["intent_confidence"] = 0.5
			context.metadata["intent_fallback"] = str(exc)
			self._log(f"Intent fallback → {context.intent} ({exc})")
		return context
