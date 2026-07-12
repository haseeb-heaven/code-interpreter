"""Integration: AgentPipeline alternate paths (safety block, repair, async)."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _stub_pipeline():
	from libs.agents.agent_pipeline import AgentPipeline

	pipeline = AgentPipeline(
		model_router=MagicMock(),
		executor=MagicMock(),
		repairer=MagicMock(),
		prompt_builder=MagicMock(),
		logger=MagicMock(),
		unsafe=False,
	)
	return pipeline


class TestPipelineSafetyBlockedPath(unittest.TestCase):
	def test_unsafe_context_skips_execute_and_still_reviews(self):
		pipeline = _stub_pipeline()

		pipeline.intent_router.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "intent", "code") or ctx
		)
		pipeline.planner.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "plan", ["blocked"]) or ctx
		)
		pipeline.executor.generate = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "code", "os.system('rm')") or ctx
		)
		pipeline.safety_guard.run = MagicMock(
			side_effect=lambda ctx: (
				setattr(ctx, "safe", False),
				setattr(ctx, "error", "dangerous"),
				ctx,
			)[-1]
		)
		pipeline.executor.execute = MagicMock(
			side_effect=AssertionError("execute must not run when unsafe")
		)
		pipeline.repairer.run = MagicMock(
			side_effect=AssertionError("repairer must not run when unsafe")
		)
		pipeline.verifier.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "verified", False) or ctx
		)
		pipeline.reviewer.run = MagicMock(
			side_effect=lambda ctx: (
				setattr(ctx, "approved", False),
				ctx.metadata.update({"review_reason": "blocked"}),
				ctx,
			)[-1]
		)

		result = pipeline.run(task="delete everything", os_name="Windows", language="python")

		self.assertFalse(result.safe)
		self.assertEqual(result.error, "dangerous")
		self.assertFalse(result.approved)
		pipeline.executor.execute.assert_not_called()
		pipeline.repairer.run.assert_not_called()
		pipeline.reviewer.run.assert_called_once()


class TestPipelineRepairPath(unittest.TestCase):
	def test_error_after_execute_invokes_repairer(self):
		pipeline = _stub_pipeline()

		pipeline.intent_router.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "intent", "code") or ctx
		)
		pipeline.planner.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "plan", ["fix"]) or ctx
		)
		pipeline.executor.generate = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "code", "print(1/0)") or ctx
		)
		pipeline.safety_guard.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "safe", True) or ctx
		)

		def _execute(ctx):
			ctx.output = ""
			ctx.error = "ZeroDivisionError"
			return ctx

		def _repair(ctx):
			ctx.code = "print(0)"
			ctx.output = "0\n"
			ctx.error = ""
			return ctx

		pipeline.executor.execute = MagicMock(side_effect=_execute)
		pipeline.repairer.run = MagicMock(side_effect=_repair)
		pipeline.verifier.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "verified", True) or ctx
		)
		pipeline.reviewer.run = MagicMock(
			side_effect=lambda ctx: (
				setattr(ctx, "approved", True),
				ctx.metadata.update({"review_reason": "repaired"}),
				ctx,
			)[-1]
		)

		result = pipeline.run(task="divide carefully", os_name="Windows", language="python")

		pipeline.repairer.run.assert_called_once()
		self.assertEqual(result.code, "print(0)")
		self.assertEqual(result.error, "")
		self.assertTrue(result.verified)
		self.assertTrue(result.approved)


class TestPipelineAsyncPath(unittest.TestCase):
	def test_run_async_happy_path_with_sync_stage_fallbacks(self):
		pipeline = _stub_pipeline()

		# Prefer async stubs so real agent run_async bodies (LLM prompts) are skipped.
		async def _intent(ctx):
			ctx.intent = "code"
			return ctx

		async def _plan(ctx):
			ctx.plan = ["async"]
			return ctx

		async def _generate(ctx):
			ctx.code = "print('async')"
			return ctx

		async def _safety(ctx):
			ctx.safe = True
			return ctx

		async def _execute(ctx):
			ctx.output = "async"
			ctx.error = ""
			return ctx

		async def _repair(ctx):
			return ctx

		async def _verify(ctx):
			ctx.verified = True
			return ctx

		async def _review(ctx):
			ctx.approved = True
			return ctx

		pipeline.intent_router.run_async = _intent
		pipeline.planner.run_async = _plan
		pipeline.executor.generate_async = _generate
		pipeline.safety_guard.run_async = _safety
		pipeline.executor.execute_async = _execute
		pipeline.repairer.run_async = _repair
		pipeline.verifier.run_async = _verify
		pipeline.reviewer.run_async = _review

		result = asyncio.run(
			pipeline.run_async(task="print async", os_name="Windows", language="python")
		)

		self.assertEqual(result.intent, "code")
		self.assertEqual(result.output, "async")
		self.assertTrue(result.verified)
		self.assertTrue(result.approved)


if __name__ == "__main__":
	unittest.main()
