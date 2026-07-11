"""Unit tests for ReAct LLM helper and AutonomousAgentLoop."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libs.agent.auto_loop import AutonomousAgentLoop
from libs.agent.llm import call_llm
from libs.tools.tool_registry import ToolRegistry
from libs.tools.base_tool import BaseTool, ToolResult


class _EchoTool(BaseTool):
	name = "echo"
	description = "Echo input"
	input_schema = {
		"type": "object",
		"properties": {"text": {"type": "string"}},
		"required": ["text"],
	}

	def run(self, input_data):
		return ToolResult(success=True, output=str(input_data.get("text", "")))


class TestCallLlm(unittest.TestCase):
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.01)
	@patch("libs.agent.llm.litellm.completion")
	def test_call_llm_success(self, completion_mock, _cost):
		completion_mock.return_value = SimpleNamespace(
			choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))],
			usage=SimpleNamespace(total_tokens=12),
		)
		content, stats = call_llm("gpt-4o", [{"role": "user", "content": "hi"}], api_key="sk-x")
		self.assertEqual(content, "hello")
		self.assertEqual(stats["tokens"], 12)
		self.assertAlmostEqual(stats["cost"], 0.01)

	@patch("libs.agent.llm.litellm.completion", side_effect=RuntimeError("down"))
	def test_call_llm_raises(self, _completion):
		with self.assertRaises(RuntimeError):
			call_llm("gpt-4o", [{"role": "user", "content": "hi"}])


class TestAutonomousAgentLoop(unittest.TestCase):
	def test_final_answer_without_tools(self):
		registry = ToolRegistry()
		registry.register(_EchoTool())

		def completion_fn(**_kwargs):
			return {
				"choices": [{"message": {"content": "done", "tool_calls": None}}],
			}

		loop = AutonomousAgentLoop(
			model="gpt-4o",
			auto_mode=True,
			registry=registry,
			completion_fn=completion_fn,
		)
		self.assertEqual(loop.run("say hi"), "done")

	def test_tool_call_then_final(self):
		registry = ToolRegistry()
		registry.register(_EchoTool())
		calls = {"n": 0}

		def completion_fn(**_kwargs):
			calls["n"] += 1
			if calls["n"] == 1:
				return {
					"choices": [{
						"message": {
							"content": None,
							"tool_calls": [{
								"id": "1",
								"type": "function",
								"function": {
									"name": "echo",
									"arguments": '{"text": "ping"}',
								},
							}],
						}
					}]
				}
			return {"choices": [{"message": {"content": "ping", "tool_calls": None}}]}

		loop = AutonomousAgentLoop(
			model="gpt-4o",
			auto_mode=True,
			registry=registry,
			completion_fn=completion_fn,
		)
		self.assertEqual(loop.run("echo ping"), "ping")
		self.assertEqual(calls["n"], 2)

	def test_denied_tool_call(self):
		registry = ToolRegistry()
		registry.register(_EchoTool())
		calls = {"n": 0}

		def completion_fn(**_kwargs):
			calls["n"] += 1
			if calls["n"] == 1:
				return {
					"choices": [{
						"message": {
							"content": None,
							"tool_calls": [{
								"id": "1",
								"function": {"name": "echo", "arguments": "{}"},
							}],
						}
					}]
				}
			return {"choices": [{"message": {"content": "denied-path", "tool_calls": None}}]}

		loop = AutonomousAgentLoop(
			model="gpt-4o",
			auto_mode=False,
			registry=registry,
			completion_fn=completion_fn,
			confirm_fn=lambda *_a, **_k: False,
		)
		self.assertEqual(loop.run("echo"), "denied-path")

	def test_parse_tool_call_invalid_json(self):
		name, args, call_id = AutonomousAgentLoop._parse_tool_call(
			{"id": "x", "function": {"name": "echo", "arguments": "{bad"}}
		)
		self.assertEqual(name, "echo")
		self.assertEqual(args, {})
		self.assertEqual(call_id, "x")


if __name__ == "__main__":
	unittest.main()
