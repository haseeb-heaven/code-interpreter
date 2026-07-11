"""Verifier agent — programmatic output checks (no LLM call)."""

from __future__ import annotations

import re

from libs.agents.base_agent import AgentContext, BaseAgent


class VerifierAgent(BaseAgent):
	def run(self, context: AgentContext) -> AgentContext:
		mode = context.metadata.get("mode") or context.intent or "code"

		# Chat/vision answers are verified as non-empty text only.
		if mode in ("chat", "vision"):
			passed, reason = self._check_not_empty(context)
			context.verified = passed
			context.metadata["verify_reason"] = reason or "Chat/vision output present"
			self._log("Verification " + ("PASSED" if passed else f"FAILED: {reason}"))
			return context

		if context.error and not context.output:
			context.verified = False
			context.metadata["verify_reason"] = "No output produced"
			self._log("Verification FAILED: No output produced")
			return context

		if not context.safe:
			context.verified = False
			context.metadata["verify_reason"] = "Skipped — safety blocked"
			return context

		checks = [
			self._check_not_empty,
			self._check_no_traceback,
			self._check_no_syntax_error,
		]

		for check in checks:
			passed, reason = check(context)
			if not passed:
				context.verified = False
				context.metadata["verify_reason"] = reason
				self._log(f"Verification FAILED: {reason}")
				return context

		context.verified = True
		context.metadata["verify_reason"] = "All checks passed"
		self._log("Verification PASSED")
		return context

	def _check_not_empty(self, ctx: AgentContext):
		if not (ctx.output or "").strip():
			return False, "Output is empty"
		return True, ""

	def _check_no_traceback(self, ctx: AgentContext):
		if "Traceback (most recent call last)" in (ctx.output or ""):
			return False, "Output contains traceback"
		return True, ""

	def _check_no_syntax_error(self, ctx: AgentContext):
		if re.search(r"SyntaxError|IndentationError|NameError", ctx.output or ""):
			return False, "Output contains Python error"
		return True, ""
