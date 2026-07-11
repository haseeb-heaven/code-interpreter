"""Async execution basics for issue #203."""

from __future__ import annotations

import asyncio
import unittest

from libs.agents.agent_pipeline import AgentPipeline
from libs.core.model_router import ModelRouter
from libs.execution.executor import CodeExecutor


class FakeLogger:
	def info(self, *args, **kwargs):
		pass

	def warning(self, *args, **kwargs):
		pass

	def error(self, *args, **kwargs):
		pass


class TestAsyncBasics(unittest.TestCase):
	def test_route_async_uses_fake_acompletion(self):
		async def fake_acompletion(model, **kwargs):
			return {"choices": [{"message": {"content": f"{model}:{kwargs['messages'][0]['content']}"}}]}

		class FakeUtilityManager:
			def _extract_content(self, response):
				return response["choices"][0]["message"]["content"]

		class FakeInterp:
			INTERPRETER_MODEL = "gpt-4o"
			config_values = {"api_base": "None"}
			utility_manager = FakeUtilityManager()
			logger = FakeLogger()

		router = ModelRouter(FakeInterp())
		result = asyncio.run(
			router.route_async(
				[{"role": "user", "content": "hello"}],
				config_values={"temperature": 0.0, "max_tokens": 16},
				acompletion_fn=fake_acompletion,
			)
		)

		self.assertEqual(result, "gpt-4o:hello")

	def test_execute_async_runs_python_code(self):
		class FakeInterp:
			UNSAFE_EXECUTION = True
			logger = FakeLogger()

		executor = CodeExecutor(FakeInterp())
		output, error = asyncio.run(executor.execute_async("print(1+1)", "python", timeout=5))

		self.assertEqual(output.strip(), "2")
		self.assertEqual(error, "")

	def test_agent_pipeline_run_async_uses_sync_fallbacks(self):
		class FakeRouter:
			def __init__(self):
				self.responses = [
					'{"intent": "code", "confidence": 1.0}',
					'{"steps": ["print two"], "mode": "code", "language": "python", "complexity": "simple"}',
					"```python\nprint(1+1)\n```",
					'{"approved": true, "reason": "output matches task"}',
				]

			def route(self, messages, config_values=None):
				return self.responses.pop(0)

		class FakeExecutor:
			def execute_generated_output(self, code, language, force_execute=False):
				return "2\n", None, None

		class FakePromptBuilder:
			def build(self, task, os_name):
				return task

		pipeline = AgentPipeline(
			model_router=FakeRouter(),
			executor=FakeExecutor(),
			repairer=object(),
			prompt_builder=FakePromptBuilder(),
			logger=FakeLogger(),
			unsafe=False,
		)

		ctx = asyncio.run(pipeline.run_async(task="print 1+1", os_name="Linux", language="python"))

		self.assertTrue(ctx.verified)
		self.assertTrue(ctx.approved)
		self.assertEqual(ctx.output, "2\n")


if __name__ == "__main__":
	unittest.main()
