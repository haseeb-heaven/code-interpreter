"""Unit tests for the multi-agent pipeline (#202)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from libs.agents.agent_pipeline import AgentPipeline
from libs.agents.base_agent import AgentContext
from libs.agents.intent_router import IntentRouter, _heuristic_intent
from libs.agents.planner_agent import PlannerAgent
from libs.agents.reviewer_agent import ReviewerAgent
from libs.agents.safety_guard import SafetyGuard
from libs.agents.verifier_agent import VerifierAgent


class FakeRouter:
	def __init__(self, responses):
		self.responses = list(responses)
		self.calls = []

	def route(self, messages, config_values=None):
		self.calls.append({"messages": messages, "config_values": config_values})
		if not self.responses:
			return "{}"
		return self.responses.pop(0)


class FakeLogger:
	def info(self, *a, **k):
		pass

	def warning(self, *a, **k):
		pass

	def error(self, *a, **k):
		pass


class TestIntentRouter(unittest.TestCase):
	def test_parses_json_intent(self):
		router = FakeRouter(['{"intent": "chat", "confidence": 0.9}'])
		agent = IntentRouter(router, FakeLogger())
		ctx = agent.run(AgentContext(task="what is recursion?", os_name="Linux", language="python"))
		self.assertEqual(ctx.intent, "chat")
		self.assertEqual(ctx.metadata["intent_confidence"], 0.9)

	def test_heuristic_fallback_on_bad_json(self):
		router = FakeRouter(["not-json-at-all"])
		agent = IntentRouter(router, FakeLogger())
		ctx = agent.run(AgentContext(task="debug this traceback please", os_name="Linux", language="python"))
		self.assertEqual(ctx.intent, "debug")

	def test_heuristic_helpers(self):
		self.assertEqual(_heuristic_intent("write unit tests for foo"), "test")
		self.assertEqual(_heuristic_intent("print hello world"), "code")


class TestPlannerAgent(unittest.TestCase):
	def test_parses_plan_json(self):
		payload = '{"steps": ["step1", "step2"], "mode": "code", "language": "python", "complexity": "simple"}'
		agent = PlannerAgent(FakeRouter([payload]), FakeLogger())
		ctx = AgentContext(task="do stuff", os_name="Linux", language="javascript", intent="code")
		ctx = agent.run(ctx)
		self.assertEqual(ctx.plan, ["step1", "step2"])
		self.assertEqual(ctx.language, "python")
		self.assertEqual(ctx.metadata["mode"], "code")

	def test_fallback_single_step(self):
		agent = PlannerAgent(FakeRouter(["nope"]), FakeLogger())
		ctx = agent.run(AgentContext(task="alone", os_name="Linux", language="python", intent="code"))
		self.assertEqual(ctx.plan, ["alone"])


class TestSafetyGuard(unittest.TestCase):
	def test_blocks_dangerous_pattern(self):
		guard = SafetyGuard(FakeRouter([]), FakeLogger(), unsafe_mode=False)
		ctx = AgentContext(task="x", os_name="Linux", language="python", code="os.system('rm -rf /')")
		ctx = guard.run(ctx)
		self.assertFalse(ctx.safe)
		self.assertIn("SafetyGuard blocked", ctx.error)

	def test_unsafe_mode_bypasses(self):
		guard = SafetyGuard(FakeRouter([]), FakeLogger(), unsafe_mode=True)
		ctx = AgentContext(task="x", os_name="Linux", language="python", code="os.system('rm -rf /')")
		ctx = guard.run(ctx)
		self.assertTrue(ctx.safe)
		self.assertEqual(ctx.metadata["safety"], "bypassed_unsafe_mode")

	def test_safe_code_passes(self):
		guard = SafetyGuard(FakeRouter([]), FakeLogger(), unsafe_mode=False)
		ctx = AgentContext(task="x", os_name="Linux", language="python", code="print(1+1)")
		ctx = guard.run(ctx)
		self.assertTrue(ctx.safe)


class TestVerifierAgent(unittest.TestCase):
	def test_empty_output_fails(self):
		agent = VerifierAgent(FakeRouter([]), FakeLogger())
		ctx = AgentContext(task="t", os_name="Linux", language="python", output="", error="")
		ctx = agent.run(ctx)
		self.assertFalse(ctx.verified)
		self.assertEqual(ctx.metadata["verify_reason"], "Output is empty")

	def test_traceback_fails(self):
		agent = VerifierAgent(FakeRouter([]), FakeLogger())
		ctx = AgentContext(
			task="t", os_name="Linux", language="python",
			output="Traceback (most recent call last):\n  File ...",
		)
		ctx = agent.run(ctx)
		self.assertFalse(ctx.verified)

	def test_clean_output_passes(self):
		agent = VerifierAgent(FakeRouter([]), FakeLogger())
		ctx = AgentContext(task="t", os_name="Linux", language="python", output="Hello World\n")
		ctx = agent.run(ctx)
		self.assertTrue(ctx.verified)


class TestReviewerAgent(unittest.TestCase):
	def test_skips_when_not_verified(self):
		agent = ReviewerAgent(FakeRouter(['{"approved": true, "reason": "ok"}']), FakeLogger())
		ctx = AgentContext(task="t", os_name="Linux", language="python", verified=False, output="x")
		ctx = agent.run(ctx)
		self.assertFalse(ctx.approved)
		self.assertIn("Skipped", ctx.metadata["review_reason"])

	def test_approves_from_json(self):
		agent = ReviewerAgent(FakeRouter(['{"approved": true, "reason": "matches task"}']), FakeLogger())
		ctx = AgentContext(task="print hi", os_name="Linux", language="python", verified=True, output="hi")
		ctx = agent.run(ctx)
		self.assertTrue(ctx.approved)
		self.assertEqual(ctx.metadata["review_reason"], "matches task")


class TestAgentPipeline(unittest.TestCase):
	def test_full_pipeline_happy_path(self):
		# intent, plan, generate code, reviewer
		responses = [
			'{"intent": "code", "confidence": 1.0}',
			'{"steps": ["print hello"], "mode": "code", "language": "python", "complexity": "simple"}',
			"```python\nprint('Hello World from Open Code Interpreter!')\nprint('Sum of 1..10 =', 55)\n```",
			'{"approved": true, "reason": "output matches task"}',
		]
		router = FakeRouter(responses)

		class FakeExecutor:
			def execute_generated_output(self, code, language, force_execute=False):
				return "Hello World from Open Code Interpreter!\nSum of 1..10 = 55\n", None, None

		class FakePromptBuilder:
			def build(self, task, os_name):
				return f"Generate code for {task}"

		class FakeRepairer:
			pass

		pipeline = AgentPipeline(
			model_router=router,
			executor=FakeExecutor(),
			repairer=FakeRepairer(),
			prompt_builder=FakePromptBuilder(),
			logger=FakeLogger(),
			unsafe=False,
		)
		ctx = pipeline.run(
			task="print a hello world message and the sum of 1 to 10",
			os_name="Linux",
			language="python",
		)
		self.assertEqual(ctx.intent, "code")
		self.assertTrue(ctx.safe)
		self.assertTrue(ctx.verified)
		self.assertTrue(ctx.approved)
		self.assertIn("Hello World", ctx.output)
		self.assertIn("Sum of 1..10 = 55", ctx.output)

	def test_pipeline_blocks_dangerous_code(self):
		responses = [
			'{"intent": "code", "confidence": 1.0}',
			'{"steps": ["wipe disk"], "mode": "code", "language": "python", "complexity": "simple"}',
			"```python\nos.system('rm -rf /')\n```",
		]
		router = FakeRouter(responses)

		class FakeExecutor:
			def execute_generated_output(self, *a, **k):
				raise AssertionError("must not execute blocked code")

		class FakePromptBuilder:
			def build(self, task, os_name):
				return task

		pipeline = AgentPipeline(
			model_router=router,
			executor=FakeExecutor(),
			repairer=MagicMock(),
			prompt_builder=FakePromptBuilder(),
			logger=FakeLogger(),
			unsafe=False,
		)
		ctx = pipeline.run(task="wipe everything", os_name="Linux", language="python")
		self.assertFalse(ctx.safe)
		self.assertFalse(ctx.verified)
		self.assertIn("SafetyGuard blocked", ctx.error)


if __name__ == "__main__":
	unittest.main()
