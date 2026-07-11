"""Unit tests for MCPClient (subprocess mocked) and ToolRegistry MCP hooks."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from libs.mcp.mcp_client import MCPClient
from libs.tools.tool_registry import ToolRegistry
from libs.tools.base_tool import ToolResult


class TestMCPClient(unittest.TestCase):
	def test_empty_command_raises(self):
		with self.assertRaises(ValueError):
			MCPClient([])

	def test_convert_to_openai_schema(self):
		schemas = MCPClient._convert_to_openai_schema(
			[{"name": "read_file", "description": "Read", "inputSchema": {"type": "object"}}]
		)
		self.assertEqual(schemas[0]["function"]["name"], "read_file")
		self.assertEqual(schemas[0]["type"], "function")

	@patch("libs.mcp.mcp_client.subprocess.Popen")
	def test_start_list_call_stop_sync(self, popen_mock):
		proc = MagicMock()
		proc.stdin = MagicMock()
		proc.stderr = MagicMock()
		proc.poll.return_value = None
		responses = [
			json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}),
			json.dumps({
				"jsonrpc": "2.0",
				"id": 2,
				"result": {
					"tools": [{
						"name": "ping",
						"description": "Ping",
						"inputSchema": {"type": "object", "properties": {}},
					}]
				},
			}),
			json.dumps({
				"jsonrpc": "2.0",
				"id": 3,
				"result": {"content": [{"type": "text", "text": "pong"}]},
			}),
		]
		proc.stdout.readline.side_effect = [r + "\n" for r in responses]
		popen_mock.return_value = proc

		client = MCPClient(["python", "-c", "pass"])
		client.start_sync()
		tools = client.list_tools_sync()
		self.assertEqual(tools[0]["function"]["name"], "ping")
		self.assertEqual(client.call_tool_sync("ping", {}), "pong")
		client.stop_sync()
		proc.terminate.assert_called()


class TestToolRegistryMcpAndSearch(unittest.TestCase):
	def test_web_search_not_enabled_message(self):
		reg = ToolRegistry()
		result = reg.call("web_search", {"query": "x"})
		self.assertFalse(result.success)
		self.assertIn("--search", result.error)

	def test_enable_web_search_duckduckgo(self):
		reg = ToolRegistry()
		tool = reg.enable_web_search(provider="duckduckgo")
		self.assertEqual(tool.name, "web_search")
		self.assertIn("web_search", reg.names())

	def test_register_mcp_tools_and_dispatch(self):
		reg = ToolRegistry()
		schemas = [{
			"type": "function",
			"function": {
				"name": "mcp_echo",
				"description": "echo",
				"parameters": {"type": "object", "properties": {}},
			},
		}]
		reg.register_mcp_tools(schemas, call_fn=lambda name, args: f"{name}:{args}")
		result = reg.dispatch("mcp_echo", {"a": 1})
		self.assertTrue(result.success)
		self.assertIn("mcp_echo", result.output)
		self.assertTrue(any(s["function"]["name"] == "mcp_echo" for s in reg.openai_schemas()))

	def test_mcp_handler_error(self):
		reg = ToolRegistry()
		schemas = [{
			"type": "function",
			"function": {"name": "bad", "description": "", "parameters": {}},
		}]

		def boom(_name, _args):
			raise RuntimeError("fail")

		reg.register_mcp_tools(schemas, call_fn=boom)
		result = reg.call("bad", {})
		self.assertFalse(result.success)
		self.assertIn("fail", result.error)


if __name__ == "__main__":
	unittest.main()
