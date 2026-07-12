"""Integration: tools registry, session store, output formatter, auto-loop (mocked)."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestToolsRegistryBootstrapIntegration(unittest.TestCase):
	def test_build_registry_registers_core_and_native_tools(self):
		from libs.tools.bootstrap import build_registry

		registry = build_registry(executor=MagicMock(), package_manager=MagicMock())
		names = {t["name"] for t in registry.list_tools()}

		self.assertIn("execute_code", names)
		self.assertIn("install_package", names)
		self.assertIn("read_file", names)
		self.assertIn("write_file", names)
		self.assertIn("list_dir", names)
		self.assertIn("run_shell", names)
		self.assertIn("glob_search", names)

	def test_enable_web_search_adds_search_tool(self):
		from libs.tools.bootstrap import build_registry

		registry = build_registry(executor=MagicMock(), package_manager=MagicMock())
		registry.enable_web_search(provider="duckduckgo")
		names = {t["name"] for t in registry.list_tools()}
		self.assertIn("web_search", names)

	def test_wire_components_enables_search_when_flag_set(self):
		from libs.core.session import wire_components

		interp = MagicMock()
		interp.args = SimpleNamespace(
			lang="python",
			mode="code",
			model="gpt-4o",
			save_code=False,
			exec=False,
			display_code=False,
			unsafe=False,
			history=False,
			file=None,
			max_context_tokens=8000,
			history_file="history/history.json",
			search=True,
			search_provider="duckduckgo",
			search_api_key=None,
		)
		interp.package_manager = MagicMock()
		interp.logger = MagicMock()
		interp.history_file = "history/history.json"
		interp.initialize_mode = MagicMock()
		interp.utility_manager = MagicMock()

		with patch("libs.key_manager.resolve_search_provider", return_value=("duckduckgo", None)):
			wire_components(interp)

		self.assertIsNotNone(interp.tool_registry)
		names = {t["name"] for t in interp.tool_registry.list_tools()}
		self.assertIn("web_search", names)
		self.assertIsNotNone(interp.memory)
		self.assertIsNotNone(interp.executor)
		self.assertIsNotNone(interp.model_router)


class TestOutputFormatterIntegration(unittest.TestCase):
	def test_from_args_json_is_structured_and_emits_object(self):
		from libs.output_formatter import OutputFormatter

		args = SimpleNamespace(output_format="json", no_color=True)
		formatter = OutputFormatter.from_args(args, isatty=True)
		self.assertTrue(formatter.is_structured)

		buf = io.StringIO()
		formatter.emit(
			result_text="done",
			code="print(1)",
			execution_output="1\n",
			error=None,
			status="success",
			file=buf,
		)
		payload = json.loads(buf.getvalue())
		self.assertEqual(payload["status"], "success")
		self.assertIn("print(1)", payload.get("code") or payload.get("result") or str(payload))

	def test_markdown_emit_contains_fenced_code(self):
		from libs.output_formatter import OutputFormatter

		args = SimpleNamespace(output_format="markdown", no_color=True)
		formatter = OutputFormatter.from_args(args, isatty=True)
		buf = io.StringIO()
		formatter.emit(
			result_text="ok",
			code="print('hi')",
			execution_output="hi\n",
			file=buf,
		)
		text = buf.getvalue()
		self.assertIn("```", text)
		self.assertIn("print('hi')", text)


class TestSessionStoreIntegration(unittest.TestCase):
	def test_session_round_trip_under_temp_dir(self):
		from libs.memory.session_store import SessionStore

		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			store = SessionStore("integ-demo", session_dir=root)
			messages = [
				{"role": "user", "content": "hello"},
				{"role": "assistant", "content": "world"},
			]
			store.save(messages, model="gpt-4o")
			loaded = store.load()

			self.assertEqual(len(loaded), 2)
			self.assertEqual(loaded[0]["content"], "hello")
			self.assertEqual(loaded[1]["content"], "world")
			self.assertTrue(store.path.exists())


class TestAutonomousLoopYoloIntegration(unittest.TestCase):
	def test_yolo_loop_dispatches_tool_then_returns_final_answer(self):
		from libs.agent.auto_loop import AutonomousAgentLoop
		from libs.tools.tool_registry import ToolRegistry
		from libs.tools import BaseTool, ToolResult

		class PingTool(BaseTool):
			name = "ping"
			description = "Ping"
			input_schema = {
				"type": "object",
				"properties": {"msg": {"type": "string"}},
				"required": ["msg"],
			}

			def run(self, input_data):
				return ToolResult(success=True, output=f"pong:{input_data['msg']}")

		registry = ToolRegistry()
		registry.register(PingTool())

		calls = {"n": 0}

		def completion_fn(model, messages, tools):
			calls["n"] += 1
			if calls["n"] == 1:
				return {
					"choices": [
						{
							"message": {
								"content": None,
								"tool_calls": [
									{
										"id": "call_1",
										"type": "function",
										"function": {
											"name": "ping",
											"arguments": json.dumps({"msg": "hi"}),
										},
									}
								],
							}
						}
					]
				}
			return {
				"choices": [
					{"message": {"content": "done with tools", "tool_calls": None}}
				]
			}

		loop = AutonomousAgentLoop(
			model="gpt-4o",
			auto_mode=True,
			registry=registry,
			completion_fn=completion_fn,
			max_iterations=5,
		)
		answer = loop.run("ping once")
		self.assertIn("done", answer)
		self.assertEqual(calls["n"], 2)


if __name__ == "__main__":
	unittest.main()
