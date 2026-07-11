"""Orchestrates the full multi-agent pipeline."""

from __future__ import annotations

import asyncio

from libs.agents.base_agent import AgentContext
from libs.agents.executor_agent import ExecutorAgent
from libs.agents.intent_router import IntentRouter
from libs.agents.planner_agent import PlannerAgent
from libs.agents.repairer_agent import RepairerAgent
from libs.agents.reviewer_agent import ReviewerAgent
from libs.agents.safety_guard import SafetyGuard
from libs.agents.verifier_agent import VerifierAgent


class AgentPipeline:
	"""
	IntentRouter → Planner → (generate) → SafetyGuard → Executor →
	Repairer (on error) → Verifier → Reviewer
	"""

	def __init__(self, model_router, executor, repairer, prompt_builder, logger, unsafe=False, code_extractor=None,
				 display_code_fn=None, display_markdown_fn=None):
		self.logger = logger
		self.intent_router = IntentRouter(model_router, logger)
		self.planner = PlannerAgent(
			model_router,
			logger,
			tool_registry=getattr(getattr(model_router, "interp", None), "tool_registry", None),
		)
		self.safety_guard = SafetyGuard(model_router, logger, unsafe_mode=unsafe)
		self.executor = ExecutorAgent(
			model_router, executor, prompt_builder, logger, code_extractor=code_extractor
		)
		self.repairer = RepairerAgent(
			model_router, repairer, logger,
			display_code_fn=display_code_fn,
			display_markdown_fn=display_markdown_fn,
		)
		self.verifier = VerifierAgent(model_router, logger)
		self.reviewer = ReviewerAgent(model_router, logger)

	def _run_sync(self, task: str, os_name: str, language: str) -> AgentContext:
		ctx = AgentContext(task=task, os_name=os_name, language=language)
		self.logger.info(f"[AgentPipeline] start task={task[:80]!r}")

		ctx = self.intent_router.run(ctx)   # 1. classify intent
		ctx = self.planner.run(ctx)         # 2. decompose task
		ctx = self.executor.generate(ctx)   # 3a. generate code/response
		ctx = self.safety_guard.run(ctx)    # 3b. pre-execution safety
		if ctx.safe:
			ctx = self.executor.execute(ctx)  # 4. run code (if any)
		else:
			self.logger.warning(f"[AgentPipeline] blocked by SafetyGuard: {ctx.error}")

		if ctx.error and ctx.safe:
			ctx = self.repairer.run(ctx)    # 5. fix errors

		ctx = self.verifier.run(ctx)        # 6. programmatic checks
		ctx = self.reviewer.run(ctx)        # 7. LLM intent match (if verified)

		self.logger.info(
			f"[AgentPipeline] done intent={ctx.intent} safe={ctx.safe} "
			f"verified={ctx.verified} approved={ctx.approved}"
		)
		return ctx

	def run(self, task: str, os_name: str, language: str) -> AgentContext:
		"""Synchronous compatibility wrapper for CLI and existing tests."""
		return self._run_sync(task=task, os_name=os_name, language=language)

	async def run_async(self, task: str, os_name: str, language: str) -> AgentContext:
		"""Preferred async entrypoint for the multi-agent pipeline."""
		ctx = AgentContext(task=task, os_name=os_name, language=language)
		self.logger.info(f"[AgentPipeline] async start task={task[:80]!r}")

		ctx = await self._call_async(self.intent_router, "run_async", "run", ctx)
		ctx = await self._call_async(self.planner, "run_async", "run", ctx)
		ctx = await self._call_async(self.executor, "generate_async", "generate", ctx)
		ctx = await self._call_async(self.safety_guard, "run_async", "run", ctx)
		if ctx.safe:
			ctx = await self._call_async(self.executor, "execute_async", "execute", ctx)
		else:
			self.logger.warning(f"[AgentPipeline] blocked by SafetyGuard: {ctx.error}")

		if ctx.error and ctx.safe:
			ctx = await self._call_async(self.repairer, "run_async", "run", ctx)

		ctx = await self._call_async(self.verifier, "run_async", "run", ctx)
		ctx = await self._call_async(self.reviewer, "run_async", "run", ctx)

		self.logger.info(
			f"[AgentPipeline] async done intent={ctx.intent} safe={ctx.safe} "
			f"verified={ctx.verified} approved={ctx.approved}"
		)
		return ctx

	async def _call_async(self, obj, async_method_name, sync_method_name, ctx):
		async_method = getattr(obj, async_method_name, None)
		if async_method:
			return await async_method(ctx)
		return await asyncio.to_thread(getattr(obj, sync_method_name), ctx)
