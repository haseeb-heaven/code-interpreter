"""Planner agent — decomposes a task into ordered steps."""

from __future__ import annotations

import json
import re

from libs.agents.base_agent import AgentContext, BaseAgent

PLANNER_SYSTEM_PROMPT = """
You are a task planner for a code execution agent.
Given a user task and its classified intent, return a JSON plan:
- steps: list of ordered sub-tasks
- mode: one of ["code", "script", "command", "vision", "chat", "debug", "review", "test"]
- language: one of ["python", "javascript"]
- complexity: one of ["simple", "moderate", "complex"]
Return ONLY valid JSON.
""".strip()


def _parse_plan_payload(text: str) -> dict:
	text = (text or "").strip()
	fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
	candidate = fence.group(1) if fence else text
	if not candidate.lstrip().startswith("{"):
		match = re.search(r"\{.*\}", text, re.DOTALL)
		if match:
			candidate = match.group(0)
	return json.loads(candidate)


class PlannerAgent(BaseAgent):
	def run(self, context: AgentContext) -> AgentContext:
		self._log(f"Planning task (intent={context.intent}): {context.task[:80]}")
		prompt = f"Task: {context.task}\nIntent: {context.intent}\nOS: {context.os_name}\nLanguage: {context.language}"
		try:
			response = self.model_router.route(
				messages=[
					{"role": "system", "content": PLANNER_SYSTEM_PROMPT},
					{"role": "user", "content": prompt},
				],
				config_values={"temperature": 0.1, "max_tokens": 512},
			)
			plan_data = _parse_plan_payload(response)
			steps = plan_data.get("steps") or [context.task]
			if not isinstance(steps, list) or not steps:
				steps = [context.task]
			context.plan = [str(step) for step in steps]
			context.metadata["mode"] = plan_data.get("mode", context.intent or "code")
			context.metadata["complexity"] = plan_data.get("complexity", "simple")
			planned_language = plan_data.get("language")
			if planned_language in ("python", "javascript"):
				context.language = planned_language
			self._log(f"Plan: {len(context.plan)} steps, mode={context.metadata['mode']}")
		except Exception as exc:
			context.plan = [context.task]
			context.metadata["mode"] = context.intent or "code"
			context.metadata["complexity"] = "simple"
			context.metadata["plan_fallback"] = str(exc)
			self._log(f"Plan fallback → single step ({exc})")
		return context
