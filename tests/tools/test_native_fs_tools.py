"""Unit tests for native FS/shell tools and ToolRegistry dispatch (#215)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from libs.tools import ToolRegistry, build_native_fs_registry
from libs.tools.builtin import (
	FileReadTool,
	FileWriteTool,
	GlobSearchTool,
	ListDirTool,
	RunShellTool,
)


class TestNativeFsTools(unittest.TestCase):
	def test_write_read_list_glob_roundtrip(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			registry = build_native_fs_registry(cwd=tmpdir, restrict_to_cwd=True)
			target = Path(tmpdir) / "nested" / "note.txt"

			write_result = registry.dispatch(
				"write_file",
				{"path": str(target), "content": "hello autonomy"},
			)
			self.assertTrue(write_result.success, write_result.error)
			self.assertTrue(target.is_file())

			read_result = registry.dispatch("read_file", {"path": str(target)})
			self.assertTrue(read_result.success)
			self.assertEqual(read_result.output, "hello autonomy")

			list_result = registry.dispatch("list_dir", {"path": str(Path(tmpdir) / "nested")})
			self.assertTrue(list_result.success)
			self.assertIn("note.txt", list_result.output)

			glob_result = registry.dispatch("glob_search", {"pattern": "**/*.txt"})
			self.assertTrue(glob_result.success)
			self.assertIn("note.txt", glob_result.output.replace("\\", "/"))

	def test_run_shell_echo(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			tool = RunShellTool(cwd=tmpdir)
			# Portable-ish: Python one-liner works on Windows and Unix
			result = tool.run(
				{
					"command": 'python -c "print(123)"',
					"timeout": 15,
				}
			)
			self.assertTrue(result.success, result.error or result.output)
			self.assertIn("123", result.output)

	def test_run_shell_timeout(self):
		tool = RunShellTool()
		with patch("libs.tools.builtin.run_shell_tool.subprocess.run") as mock_run:
			mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=1)
			result = tool.run({"command": "sleep 99", "timeout": 1})
		self.assertFalse(result.success)
		self.assertIn("timed out", result.error)

	def test_openai_schemas_include_five_native_tools(self):
		registry = build_native_fs_registry()
		schemas = registry.openai_schemas()
		names = {s["function"]["name"] for s in schemas}
		self.assertEqual(
			names,
			{"read_file", "write_file", "list_dir", "run_shell", "glob_search"},
		)
		for schema in schemas:
			self.assertEqual(schema["type"], "function")
			self.assertIn("parameters", schema["function"])

	def test_dispatch_unknown_tool(self):
		registry = ToolRegistry()
		result = registry.dispatch("nope", {})
		self.assertFalse(result.success)
		self.assertIn("Unknown tool", result.error)

	def test_write_restrict_to_cwd(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			tool = FileWriteTool(cwd=tmpdir, restrict_to_cwd=True)
			outside = Path(tmpdir).parent / f"oci-outside-{os.getpid()}.txt"
			try:
				result = tool.run({"path": str(outside), "content": "x"})
				self.assertFalse(result.success)
				self.assertIn("outside", result.error.lower())
			finally:
				if outside.exists():
					outside.unlink()


class TestMcpRegistration(unittest.TestCase):
	def test_register_mcp_tools_and_dispatch(self):
		registry = ToolRegistry()
		calls = []

		def call_fn(name, args):
			calls.append((name, args))
			return f"ok:{name}"

		schemas = [
			{
				"type": "function",
				"function": {
					"name": "mcp_echo",
					"description": "echo",
					"parameters": {
						"type": "object",
						"properties": {"text": {"type": "string"}},
					},
				},
			}
		]
		registry.register_mcp_tools(schemas, call_fn)
		self.assertIn("mcp_echo", registry.names())
		result = registry.dispatch("mcp_echo", {"text": "hi"})
		self.assertTrue(result.success)
		self.assertEqual(result.output, "ok:mcp_echo")
		self.assertEqual(calls, [("mcp_echo", {"text": "hi"})])


if __name__ == "__main__":
	unittest.main()
