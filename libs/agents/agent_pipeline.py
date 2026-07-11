"""Orchestrates the full multi-agent pipeline."""

from __future__ import annotations

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
		self.planner = PlannerAgent(model_router, logger)
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

	def run(self, task: str, os_name: str, language: str) -> AgentContext:
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
