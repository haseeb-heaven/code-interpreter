"""TC005 — Agent SafetyGuard blocks dangerous code before execution."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

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
	def execute_generated_output(self, *a, **k):
		raise AssertionError("Executor must not run SafetyGuard-blocked code")


class _FakePromptBuilder:
	def build(self, task, os_name):
		return task


class TC005_Agent_SafetyGuard_Blocks_Before_Execution(unittest.TestCase):
	def test_dangerous_code_blocked(self):
		responses = [
			'{"intent": "code", "confidence": 1.0}',
			'{"steps": ["wipe disk"], "mode": "code", "language": "python", "complexity": "simple"}',
			"```python\nos.system('rm -rf /')\n```",
		]
		pipeline = AgentPipeline(
			model_router=_FakeRouter(responses),
			executor=_FakeExecutor(),
			repairer=MagicMock(),
			prompt_builder=_FakePromptBuilder(),
			logger=_FakeLogger(),
			unsafe=False,
		)
		ctx = pipeline.run(task="wipe everything", os_name="Linux", language="python")
		self.assertFalse(ctx.safe)
		self.assertIn("SafetyGuard blocked", ctx.error)
		self.assertFalse(ctx.verified)


if __name__ == "__main__":
	unittest.main()
