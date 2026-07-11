"""Unit tests for RepairerAgent and ReviewerAgent (mocked collaborators)."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from libs.agents.base_agent import AgentContext
from libs.agents.repairer_agent import RepairerAgent
from libs.agents.reviewer_agent import ReviewerAgent, _parse_review_payload


def _ctx(**kwargs):
	base = dict(
		task="print hello",
		os_name="Windows",
		language="python",
		intent="code",
		plan=["print"],
		code="print('x')",
		output="",
		error="",
		safe=True,
		verified=True,
		approved=False,
		metadata={},
	)
	base.update(kwargs)
	return AgentContext(**base)


class TestRepairerAgent(unittest.TestCase):
	def test_no_error_is_noop(self):
		agent = RepairerAgent(MagicMock(), MagicMock(), MagicMock())
		ctx = _ctx(error="")
		out = agent.run(ctx)
		self.assertIs(out, ctx)
		self.assertFalse(out.metadata.get("repaired"))

	def test_safety_block_skips_repair(self):
		repairer = MagicMock()
		agent = RepairerAgent(MagicMock(), repairer, MagicMock())
		ctx = _ctx(error="SafetyGuard blocked: rm -rf")
		out = agent.run(ctx)
		repairer.attempt_repair_after_failure.assert_not_called()
		self.assertEqual(out.error, "SafetyGuard blocked: rm -rf")

	def test_attempt_repair_after_failure(self):
		repairer = MagicMock()
		repairer.attempt_repair_after_failure.return_value = (
			"print('hello')",
			"hello",
			"",
		)
		agent = RepairerAgent(MagicMock(), repairer, MagicMock())
		ctx = _ctx(error="NameError: x")
		out = agent.run(ctx)
		self.assertEqual(out.code, "print('hello')")
		self.assertEqual(out.output, "hello")
		self.assertEqual(out.error, "")
		self.assertTrue(out.metadata["repaired"])

	def test_run_async_uses_async_api(self):
		repairer = MagicMock()
		repairer.attempt_repair_async = AsyncMock(
			return_value=("print(1)", "1", "")
		)
		agent = RepairerAgent(MagicMock(), repairer, MagicMock())
		ctx = _ctx(error="boom")
		out = asyncio.run(agent.run_async(ctx))
		self.assertEqual(out.code, "print(1)")
		self.assertTrue(out.metadata["repaired"])


class TestReviewerAgent(unittest.TestCase):
	def test_parse_review_payload_fenced(self):
		payload = _parse_review_payload('```json\n{"approved": false, "reason": "no"}\n```')
		self.assertFalse(payload["approved"])

	def test_skip_when_not_verified(self):
		agent = ReviewerAgent(MagicMock(), MagicMock())
		ctx = _ctx(verified=False)
		out = agent.run(ctx)
		self.assertFalse(out.approved)
		self.assertIn("verification failed", out.metadata["review_reason"])

	def test_approve_from_router(self):
		router = MagicMock()
		router.route.return_value = '{"approved": true, "reason": "ok"}'
		agent = ReviewerAgent(router, MagicMock())
		out = agent.run(_ctx(verified=True, output="hello"))
		self.assertTrue(out.approved)
		self.assertEqual(out.metadata["review_reason"], "ok")

	def test_fallback_approve_on_bad_json(self):
		router = MagicMock()
		router.route.return_value = "not-json"
		agent = ReviewerAgent(router, MagicMock())
		out = agent.run(_ctx(verified=True, output="hello"))
		self.assertTrue(out.approved)
		self.assertIn("fallback", out.metadata["review_reason"].lower())


if __name__ == "__main__":
	unittest.main()
