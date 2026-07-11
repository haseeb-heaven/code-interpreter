"""Executor agent — generates code for plan steps, then runs it."""

from __future__ import annotations

import asyncio
import re

from libs.agents.base_agent import AgentContext, BaseAgent
from libs.memory.memory_entry import MemoryEntry


def _extract_code_block(text: str) -> str:
	"""Pull the first fenced code block, or return the raw text."""
	if not text:
		return ""
	match = re.search(r"```(?:\w+)?\s*([\s\S]*?)```", text)
	if match:
		return match.group(1).strip()
	return text.strip()


class ExecutorAgent(BaseAgent):
	def __init__(self, model_router, executor, prompt_builder, logger, code_extractor=None):
		super().__init__(model_router, logger)
		self.executor = executor
		self.prompt_builder = prompt_builder
		self.code_extractor = code_extractor

	def generate(self, context: AgentContext) -> AgentContext:
		"""Generate code (or chat answer) for the planned steps without executing."""
		mode = context.metadata.get("mode") or context.intent or "code"
		memory_note = self._memory_context_note(context)
		if mode in ("chat", "vision"):
			self._log(f"Generating {mode} response (no code execution)")
			prompt = self.prompt_builder.build(context.task, context.os_name) or context.task
			prompt += memory_note
			response = self.model_router.route(
				messages=[{"role": "user", "content": prompt}],
				config_values={},
			)
			context.output = response or ""
			context.code = ""
			context.metadata["executor_phase"] = "chat_response"
			self._remember_success(context)
			return context

		steps = context.plan or [context.task]
		generated_chunks = []
		for step in steps:
			self._log(f"Generating code for step: {str(step)[:60]}")
			prompt = self.prompt_builder.build(str(step), context.os_name) or str(step)
			prompt += memory_note
			raw = self.model_router.route(
				messages=[{"role": "user", "content": prompt}],
				config_values={},
			)
			if self.code_extractor:
				snippet = self.code_extractor(raw, "```", "```") or _extract_code_block(raw)
			else:
				snippet = _extract_code_block(raw)
			if snippet:
				generated_chunks.append(snippet)

		context.code = "\n\n".join(generated_chunks).strip()
		context.metadata["executor_phase"] = "generated"
		self._log(f"Generated {len(context.code)} chars of code across {len(generated_chunks)} step(s)")
		return context

	async def generate_async(self, context: AgentContext) -> AgentContext:
		"""Async code/response generation using ModelRouter.route_async when available."""
		route_async = getattr(self.model_router, "route_async", None)
		if not route_async:
			return await asyncio.to_thread(self.generate, context)

		mode = context.metadata.get("mode") or context.intent or "code"
		memory_note = self._memory_context_note(context)
		if mode in ("chat", "vision"):
			self._log(f"Generating {mode} response (no code execution)")
			prompt = self.prompt_builder.build(context.task, context.os_name) or context.task
			prompt += memory_note
			response = await route_async(
				messages=[{"role": "user", "content": prompt}],
				config_values={},
			)
			context.output = response or ""
			context.code = ""
			context.metadata["executor_phase"] = "chat_response"
			self._remember_success(context)
			return context

		steps = context.plan or [context.task]
		generated_chunks = []
		for step in steps:
			self._log(f"Generating code for step: {str(step)[:60]}")
			prompt = self.prompt_builder.build(str(step), context.os_name) or str(step)
			prompt += memory_note
			raw = await route_async(
				messages=[{"role": "user", "content": prompt}],
				config_values={},
			)
			if self.code_extractor:
				snippet = self.code_extractor(raw, "```", "```") or _extract_code_block(raw)
			else:
				snippet = _extract_code_block(raw)
			if snippet:
				generated_chunks.append(snippet)

		context.code = "\n\n".join(generated_chunks).strip()
		context.metadata["executor_phase"] = "generated"
		self._log(f"Generated {len(context.code)} chars of code across {len(generated_chunks)} step(s)")
		return context

	def execute(self, context: AgentContext) -> AgentContext:
		"""Run ``context.code`` via the existing CodeExecutor."""
		if not context.safe:
			self._log("Skipping execution — SafetyGuard blocked")
			return context

		mode = context.metadata.get("mode") or context.intent or "code"
		if mode in ("chat", "vision"):
			# Already produced output during generate().
			return context

		if not context.code:
			context.error = context.error or "ExecutorAgent: no code to execute"
			return context

		self._log("Executing generated code")
		# Prefer the sandbox-aware wrapper when available.
		if hasattr(self.executor, "execute_generated_output"):
			output, error, sandbox_ctx = self.executor.execute_generated_output(
				context.code, context.language, force_execute=True
			)
			if sandbox_ctx and hasattr(self.executor, "interp"):
				self.executor.interp.safety_manager.cleanup_sandbox_context(sandbox_ctx)
		elif hasattr(self.executor, "execute_code"):
			output, error = self.executor.execute_code(
				context.code, context.language, force_execute=True
			)
		else:
			output, error, _ = self.executor.execute(context.code, context.language)

		context.output = output or ""
		context.error = error or ""
		context.metadata["executor_phase"] = "executed"
		if context.error:
			self._log(f"Execution error: {context.error[:100]}")
		else:
			self._log(f"Execution ok ({len(context.output)} chars output)")
			self._remember_success(context)
		return context

	async def execute_async(self, context: AgentContext) -> AgentContext:
		"""Run ``context.code`` via the async executor when available."""
		if not context.safe:
			self._log("Skipping execution — SafetyGuard blocked")
			return context

		mode = context.metadata.get("mode") or context.intent or "code"
		if mode in ("chat", "vision"):
			return context

		if not context.code:
			context.error = context.error or "ExecutorAgent: no code to execute"
			return context

		execute_async = getattr(self.executor, "execute_async", None)
		if not execute_async:
			return await asyncio.to_thread(self.execute, context)

		self._log("Executing generated code asynchronously")
		output, error = await execute_async(context.code, context.language)
		context.output = output or ""
		context.error = error or ""
		context.metadata["executor_phase"] = "executed"
		if context.error:
			self._log(f"Execution error: {context.error[:100]}")
		else:
			self._log(f"Execution ok ({len(context.output)} chars output)")
			self._remember_success(context)
		return context

	def run(self, context: AgentContext) -> AgentContext:
		"""Generate then execute (used when SafetyGuard already passed / not used)."""
		context = self.generate(context)
		return self.execute(context)

	async def run_async(self, context: AgentContext) -> AgentContext:
		"""Generate then execute asynchronously."""
		context = await self.generate_async(context)
		return await self.execute_async(context)

	def _memory(self):
		interp = getattr(self.model_router, "interp", None)
		return getattr(interp, "memory", None)

	def _memory_context_note(self, context: AgentContext) -> str:
		memory = self._memory()
		if not memory:
			return ""
		try:
			memory_context = memory.get_context(context.task)
		except Exception as exception:
			self._log(f"Memory retrieval skipped: {exception}")
			return ""
		context.metadata["memory_context"] = memory_context
		if not memory_context:
			return ""
		return f"\n\nRelevant memory context:\n{memory_context}"

	def _remember_success(self, context: AgentContext) -> None:
		memory = self._memory()
		content = context.output or context.code
		if not memory or context.error or not content:
			return
		tags = [tag for tag in [context.intent, context.metadata.get("mode"), context.metadata.get("executor_phase")] if tag]
		try:
			memory.add(
				MemoryEntry(
					role="assistant",
					content=content,
					task=context.task,
					success=True,
					tags=tags,
				)
			)
		except Exception as exception:
			self._log(f"Memory save skipped: {exception}")
