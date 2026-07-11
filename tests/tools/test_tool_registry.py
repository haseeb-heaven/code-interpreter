"""Unit tests for the tool registry (#205)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from libs.tools import BaseTool, ToolRegistry, ToolResult
from libs.tools.builtin import FileReadTool


class EchoTool(BaseTool):
	name = "echo"
	description = "Echo input text."
	input_schema = {
		"type": "object",
		"properties": {
			"text": {"type": "string"},
		},
		"required": ["text"],
	}

	def run(self, input_data):
		return ToolResult(success=True, output=input_data["text"])


class TestToolRegistry(unittest.TestCase):
	def test_register_and_list_tools(self):
		registry = ToolRegistry()
		registry.register(EchoTool())

		tools = registry.list_tools()

		self.assertEqual(len(tools), 1)
		self.assertEqual(tools[0]["name"], "echo")
		self.assertEqual(tools[0]["description"], "Echo input text.")
		self.assertEqual(tools[0]["input_schema"], EchoTool.input_schema)

	def test_call_unknown_tool_returns_failure_result(self):
		registry = ToolRegistry()

		result = registry.call("missing", {})

		self.assertFalse(result.success)
		self.assertEqual(result.error, "Unknown tool: missing")

	def test_call_file_read_tool_on_temp_file(self):
		registry = ToolRegistry()
		registry.register(FileReadTool())

		with tempfile.TemporaryDirectory() as tmpdir:
			file_path = Path(tmpdir) / "sample.txt"
			file_path.write_text("hello from registry", encoding="utf-8")

			result = registry.call("read_file", {"path": str(file_path)})

		self.assertTrue(result.success)
		self.assertEqual(result.output, "hello from registry")
		self.assertEqual(result.metadata["path"], str(file_path.resolve()))

	def test_duplicate_register_raises(self):
		registry = ToolRegistry()
		registry.register(EchoTool())

		with self.assertRaises(ValueError):
			registry.register(EchoTool())


if __name__ == "__main__":
	unittest.main()
