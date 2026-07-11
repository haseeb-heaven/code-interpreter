"""Repairer agent — wraps the existing bounded repair loop."""

from __future__ import annotations

import asyncio

from libs.agents.base_agent import AgentContext, BaseAgent


class RepairerAgent(BaseAgent):
	def __init__(self, model_router, repairer, logger, display_code_fn=None, display_markdown_fn=None):
		super().__init__(model_router, logger)
		self.repairer = repairer
		self.display_code_fn = display_code_fn or (lambda *a, **k: None)
		self.display_markdown_fn = display_markdown_fn or (lambda *a, **k: None)

	def run(self, context: AgentContext) -> AgentContext:
		if not context.error:
			return context
		if context.error.startswith("SafetyGuard blocked") or context.error.startswith("Safety blocked:"):
			self._log("Skipping repair — safety block is not repairable")
			return context

		self._log(f"Repairing error: {context.error[:80]}")
		# Prefer the full attempt_repair_after_failure API from libs.execution.repairer.
		if hasattr(self.repairer, "attempt_repair_after_failure"):
			fixed_code, output, error = self.repairer.attempt_repair_after_failure(
				task=context.task,
				prompt=context.task,
				code_snippet=context.code,
				code_error=context.error,
				os_name=context.os_name,
				start_sep="```",
				end_sep="```",
				extracted_file_name=None,
				code_output=context.output or None,
				display_code_fn=self.display_code_fn,
				display_markdown_fn=self.display_markdown_fn,
			)
		elif hasattr(self.repairer, "attempt_repair"):
			fixed_code, output, error = self.repairer.attempt_repair(
				task=context.task,
				code_snippet=context.code,
				code_error=context.error,
				os_name=context.os_name,
			)
		else:
			self._log("No compatible repairer API — leaving context unchanged")
			return context

		context.code = fixed_code or context.code
		context.output = output or ""
		context.error = error or ""
		context.metadata["repaired"] = True
		return context

	async def run_async(self, context: AgentContext) -> AgentContext:
		if not context.error:
			return context
		if context.error.startswith("SafetyGuard blocked") or context.error.startswith("Safety blocked:"):
			self._log("Skipping repair — safety block is not repairable")
			return context

		attempt_repair_async = getattr(self.repairer, "attempt_repair_async", None)
		if not attempt_repair_async:
			return await asyncio.to_thread(self.run, context)

		self._log(f"Repairing error: {context.error[:80]}")
		fixed_code, output, error = await attempt_repair_async(
			task=context.task,
			prompt=context.task,
			code_snippet=context.code,
			code_error=context.error,
			os_name=context.os_name,
			start_sep="```",
			end_sep="```",
			extracted_file_name=None,
			code_output=context.output or None,
			display_code_fn=self.display_code_fn,
			display_markdown_fn=self.display_markdown_fn,
		)
		context.code = fixed_code or context.code
		context.output = output or ""
		context.error = error or ""
		context.metadata["repaired"] = True
		return context
