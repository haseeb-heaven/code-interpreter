"""Unit tests for MCPClient handshake and schema conversion (#215)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from libs.mcp.mcp_client import MCPClient


class TestMCPClient(unittest.TestCase):
	def test_convert_to_openai_schema(self):
		mcp_tools = [
			{
				"name": "read_file",
				"description": "Read a file",
				"inputSchema": {
					"type": "object",
					"properties": {"path": {"type": "string"}},
					"required": ["path"],
				},
			},
			{"name": "noop", "description": "", "inputSchema": {}},
		]
		schemas = MCPClient._convert_to_openai_schema(mcp_tools)
		self.assertEqual(len(schemas), 2)
		self.assertEqual(schemas[0]["type"], "function")
		self.assertEqual(schemas[0]["function"]["name"], "read_file")
		self.assertEqual(schemas[0]["function"]["parameters"]["required"], ["path"])

	def test_empty_command_raises(self):
		with self.assertRaises(ValueError):
			MCPClient([])

	def test_start_list_call_stop_with_mocked_process(self):
		client = MCPClient(["fake-mcp-server"])

		responses = [
			# initialize result
			{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}},
			# tools/list
			{
				"jsonrpc": "2.0",
				"id": 2,
				"result": {
					"tools": [
						{
							"name": "ping",
							"description": "Ping",
							"inputSchema": {"type": "object", "properties": {}},
						}
					]
				},
			},
			# tools/call
			{
				"jsonrpc": "2.0",
				"id": 3,
				"result": {"content": [{"type": "text", "text": "pong"}]},
			},
		]
		response_iter = iter(responses)

		mock_proc = MagicMock()
		mock_proc.stdin = MagicMock()
		mock_proc.stdout = MagicMock()
		mock_proc.stderr = MagicMock()
		mock_proc.poll.return_value = None

		def readline():
			try:
				payload = next(response_iter)
			except StopIteration:
				return ""
			return json.dumps(payload) + "\n"

		mock_proc.stdout.readline.side_effect = readline

		with patch("libs.mcp.mcp_client.subprocess.Popen", return_value=mock_proc):
			client.start_sync()
			tools = client.list_tools_sync()
			self.assertEqual(tools[0]["function"]["name"], "ping")
			result = client.call_tool_sync("ping", {})
			self.assertEqual(result, "pong")
			client.stop_sync()

		mock_proc.terminate.assert_called()
		# initialize + initialized notification + tools/list + tools/call
		self.assertGreaterEqual(mock_proc.stdin.write.call_count, 3)


if __name__ == "__main__":
	unittest.main()
