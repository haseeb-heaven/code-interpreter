"""Pre-execution safety guard — blocks dangerous code patterns."""

from __future__ import annotations

import asyncio
import re

from libs.agents.base_agent import AgentContext, BaseAgent

DANGEROUS_PATTERNS = [
	r"os\.system\s*\(.*rm\s+-rf",
	r"subprocess.*shell\s*=\s*True.*rm",
	r"shutil\.rmtree\s*\(\s*['\"]/",
	r"open\s*\(.*['\"]/etc/passwd",
	r"__import__\s*\(\s*['\"]os['\"]\s*\)",
]


class SafetyGuard(BaseAgent):
	def __init__(self, model_router, logger, unsafe_mode: bool = False):
		super().__init__(model_router, logger)
		self.unsafe_mode = unsafe_mode

	def run(self, context: AgentContext) -> AgentContext:
		if self.unsafe_mode:
			context.safe = True
			context.metadata["safety"] = "bypassed_unsafe_mode"
			self._log("Unsafe mode — safety check bypassed")
			return context

		if not context.code:
			context.safe = True
			context.metadata["safety"] = "no_code"
			return context

		for pattern in DANGEROUS_PATTERNS:
			if re.search(pattern, context.code, re.IGNORECASE | re.DOTALL):
				context.safe = False
				context.error = f"SafetyGuard blocked execution: matched pattern [{pattern}]"
				context.metadata["safety"] = "blocked"
				context.metadata["blocked_pattern"] = pattern
				self._log(f"BLOCKED: {context.error}")
				return context

		context.safe = True
		context.metadata["safety"] = "passed"
		self._log("Code passed safety check")
		return context

	async def run_async(self, context: AgentContext) -> AgentContext:
		return await asyncio.to_thread(self.run, context)
