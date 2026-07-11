"""Unit tests for IntentRouter and ExecutorAgent (mocked routers/executors)."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from libs.agents.base_agent import AgentContext
from libs.agents.executor_agent import ExecutorAgent, _extract_code_block
from libs.agents.intent_router import (
	IntentRouter,
	_heuristic_intent,
	_parse_intent_payload,
)


def _ctx(**kwargs):
	base = dict(
		task="print hello",
		os_name="Windows",
		language="python",
		intent="code",
		plan=["print hello"],
		code="",
		output="",
		error="",
		safe=True,
		verified=False,
		approved=False,
		metadata={},
	)
	base.update(kwargs)
	return AgentContext(**base)


class TestIntentHelpers(unittest.TestCase):
	def test_heuristic_matrix(self):
		self.assertEqual(_heuristic_intent("debug this traceback"), "debug")
		self.assertEqual(_heuristic_intent("please code review my module"), "review")
		self.assertEqual(_heuristic_intent("write unit tests for foo"), "test")
		self.assertEqual(_heuristic_intent("describe this screenshot"), "vision")
		self.assertEqual(_heuristic_intent("write a bash script to backup"), "script")
		self.assertEqual(_heuristic_intent("run dir"), "command")
		self.assertEqual(_heuristic_intent("what is asyncio?"), "chat")
		self.assertEqual(_heuristic_intent("print the numbers 1..10"), "code")

	def test_parse_intent_payload_variants(self):
		fenced = _parse_intent_payload('```json\n{"intent": "chat", "confidence": 0.9}\n```')
		self.assertEqual(fenced["intent"], "chat")
		embedded = _parse_intent_payload('Sure. {"intent": "code", "confidence": 1.0} done.')
		self.assertEqual(embedded["intent"], "code")


class TestIntentRouter(unittest.TestCase):
	def test_run_uses_router_json(self):
		router = MagicMock()
		router.route.return_value = '{"intent": "script", "confidence": 0.8}'
		agent = IntentRouter(router, MagicMock())
		out = agent.run(_ctx(task="write a bash script"))
		self.assertEqual(out.intent, "script")
		self.assertEqual(out.metadata["intent_confidence"], 0.8)

	def test_run_falls_back_on_invalid_intent(self):
		router = MagicMock()
		router.route.return_value = '{"intent": "nope", "confidence": 1.0}'
		agent = IntentRouter(router, MagicMock())
		out = agent.run(_ctx(task="explain generators"))
		self.assertEqual(out.intent, "chat")

	def test_run_falls_back_on_exception(self):
		router = MagicMock()
		router.route.side_effect = RuntimeError("down")
		agent = IntentRouter(router, MagicMock())
		out = agent.run(_ctx(task="fix this exception"))
		self.assertEqual(out.intent, "debug")
		self.assertIn("intent_fallback", out.metadata)

	def test_run_async_without_route_async(self):
		router = MagicMock()
		del router.route_async
		router.route.return_value = '{"intent": "code", "confidence": 1.0}'
		agent = IntentRouter(router, MagicMock())
		out = asyncio.run(agent.run_async(_ctx(task="print 1")))
		self.assertEqual(out.intent, "code")

	def test_run_async_with_route_async(self):
		router = MagicMock()
		router.route_async = AsyncMock(return_value='{"intent": "vision", "confidence": 0.7}')
		agent = IntentRouter(router, MagicMock())
		out = asyncio.run(agent.run_async(_ctx(task="look at photo")))
		self.assertEqual(out.intent, "vision")


class TestExecutorAgent(unittest.TestCase):
	def test_extract_code_block(self):
		self.assertEqual(_extract_code_block("```python\nprint(1)\n```"), "print(1)")
		self.assertEqual(_extract_code_block("bare"), "bare")
		self.assertEqual(_extract_code_block(""), "")

	def test_generate_code_mode(self):
		router = MagicMock()
		router.route.return_value = "```python\nprint('hi')\n```"
		prompt_builder = MagicMock()
		prompt_builder.build.return_value = "prompt"
		agent = ExecutorAgent(router, MagicMock(), prompt_builder, MagicMock())
		out = agent.generate(_ctx(plan=["step1"]))
		self.assertIn("print('hi')", out.code)
		self.assertEqual(out.metadata["executor_phase"], "generated")

	def test_generate_chat_mode(self):
		router = MagicMock()
		router.route.return_value = "hello there"
		prompt_builder = MagicMock()
		prompt_builder.build.return_value = "chat prompt"
		agent = ExecutorAgent(router, MagicMock(), prompt_builder, MagicMock())
		out = agent.generate(_ctx(intent="chat", metadata={"mode": "chat"}))
		self.assertEqual(out.output, "hello there")
		self.assertEqual(out.code, "")
		self.assertEqual(out.metadata["executor_phase"], "chat_response")

	def test_execute_skips_when_unsafe(self):
		agent = ExecutorAgent(MagicMock(), MagicMock(), MagicMock(), MagicMock())
		out = agent.execute(_ctx(safe=False, code="print(1)"))
		self.assertEqual(out.code, "print(1)")
		self.assertNotEqual(out.metadata.get("executor_phase"), "executed")

	def test_execute_via_generated_output(self):
		executor = MagicMock()
		executor.execute_generated_output.return_value = ("ok", "", {"sandbox": True})
		executor.interp = MagicMock()
		agent = ExecutorAgent(MagicMock(), executor, MagicMock(), MagicMock())
		out = agent.execute(_ctx(code="print(1)", language="python"))
		self.assertEqual(out.output, "ok")
		self.assertEqual(out.metadata["executor_phase"], "executed")
		executor.interp.safety_manager.cleanup_sandbox_context.assert_called_once()

	def test_execute_missing_code(self):
		agent = ExecutorAgent(MagicMock(), MagicMock(), MagicMock(), MagicMock())
		out = agent.execute(_ctx(code=""))
		self.assertIn("no code", out.error)

	def test_run_generate_then_execute(self):
		router = MagicMock()
		router.route.return_value = "```\nprint(2)\n```"
		prompt_builder = MagicMock()
		prompt_builder.build.return_value = "p"
		executor = MagicMock()
		executor.execute_generated_output.return_value = ("2", "", None)
		agent = ExecutorAgent(router, executor, prompt_builder, MagicMock())
		out = agent.run(_ctx(plan=["print 2"]))
		self.assertEqual(out.output, "2")

	def test_execute_async_uses_executor(self):
		executor = MagicMock()
		executor.execute_async = AsyncMock(return_value=("async-ok", ""))
		agent = ExecutorAgent(MagicMock(), executor, MagicMock(), MagicMock())
		out = asyncio.run(agent.execute_async(_ctx(code="print(1)")))
		self.assertEqual(out.output, "async-ok")


if __name__ == "__main__":
	unittest.main()
