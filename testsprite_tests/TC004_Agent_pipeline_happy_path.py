"""TC004 — Agent pipeline happy path with mocked LLM (backend integration)."""

from __future__ import annotations

import unittest

from libs.agents.agent_pipeline import AgentPipeline


class _FakeRouter:
	def __init__(self, responses):
		self.responses = list(responses)

	def route(self, messages, config_values=None):
		if not self.responses:
			return "{}"
		return self.responses.pop(0)


class _FakeLogger:
	def info(self, *a, **k):
		pass

	def warning(self, *a, **k):
		pass

	def error(self, *a, **k):
		pass


class _FakeExecutor:
	def execute_generated_output(self, code, language, force_execute=False):
		return (
			"Hello World from Open Code Interpreter!\nSum of 1..10 = 55\n",
			None,
			None,
		)


class _FakePromptBuilder:
	def build(self, task, os_name):
		return f"Generate code for {task}"


class TC004_Agent_Pipeline_Happy_Path(unittest.TestCase):
	def test_pipeline_approves_simple_task(self):
		responses = [
			'{"intent": "code", "confidence": 1.0}',
			'{"steps": ["print hello"], "mode": "code", "language": "python", "complexity": "simple"}',
			"```python\nprint('Hello World from Open Code Interpreter!')\nprint('Sum of 1..10 =', 55)\n```",
			'{"approved": true, "reason": "output matches task"}',
		]
		pipeline = AgentPipeline(
			model_router=_FakeRouter(responses),
			executor=_FakeExecutor(),
			repairer=object(),
			prompt_builder=_FakePromptBuilder(),
			logger=_FakeLogger(),
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


if __name__ == "__main__":
	unittest.main()
