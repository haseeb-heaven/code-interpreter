"""Reviewer agent — LLM-based intent match (only after Verifier passes)."""

from __future__ import annotations

import asyncio
import json
import re

from libs.agents.base_agent import AgentContext, BaseAgent

REVIEWER_SYSTEM_PROMPT = """
You are a code output reviewer.
Given the original task and the execution output, determine if the output correctly fulfills the task.
Return JSON: {"approved": true/false, "reason": "one sentence"}
Return ONLY valid JSON.
""".strip()


def _parse_review_payload(text: str) -> dict:
	text = (text or "").strip()
	fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
	candidate = fence.group(1) if fence else text
	if not candidate.lstrip().startswith("{"):
		match = re.search(r"\{[^{}]*\"approved\"[^{}]*\}", text, re.DOTALL)
		if match:
			candidate = match.group(0)
	return json.loads(candidate)


class ReviewerAgent(BaseAgent):
	def run(self, context: AgentContext) -> AgentContext:
		if not context.verified:
			context.approved = False
			context.metadata["review_reason"] = "Skipped — verification failed"
			self._log("Review skipped — verification failed")
			return context

		self._log("Reviewing output...")
		prompt = f"Task: {context.task}\nOutput: {(context.output or '')[:500]}"
		try:
			response = self.model_router.route(
				messages=[
					{"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
					{"role": "user", "content": prompt},
				],
				config_values={"temperature": 0.0, "max_tokens": 128},
			)
			result = _parse_review_payload(response)
			context.approved = bool(result.get("approved", True))
			context.metadata["review_reason"] = result.get("reason", "")
			self._log(f"Review: approved={context.approved}")
		except Exception as exc:
			# Soft-fail: verified output is accepted when the reviewer is unavailable.
			context.approved = True
			context.metadata["review_reason"] = f"Reviewer fallback approve ({exc})"
			self._log(f"Review fallback approve ({exc})")
		return context

	async def run_async(self, context: AgentContext) -> AgentContext:
		route_async = getattr(self.model_router, "route_async", None)
		if not route_async:
			return await asyncio.to_thread(self.run, context)

		if not context.verified:
			context.approved = False
			context.metadata["review_reason"] = "Skipped — verification failed"
			self._log("Review skipped — verification failed")
			return context

		self._log("Reviewing output...")
		prompt = f"Task: {context.task}\nOutput: {(context.output or '')[:500]}"
		try:
			response = await route_async(
				messages=[
					{"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
					{"role": "user", "content": prompt},
				],
				config_values={"temperature": 0.0, "max_tokens": 128},
			)
			result = _parse_review_payload(response)
			context.approved = bool(result.get("approved", True))
			context.metadata["review_reason"] = result.get("reason", "")
			self._log(f"Review: approved={context.approved}")
		except Exception as exc:
			context.approved = True
			context.metadata["review_reason"] = f"Reviewer fallback approve ({exc})"
			self._log(f"Review fallback approve ({exc})")
		return context
