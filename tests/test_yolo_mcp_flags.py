"""CLI flag tests for --yolo / --mcp-server (#215)."""

from __future__ import annotations

import unittest

import interpreter as interpreter_mod


class TestYoloMcpFlags(unittest.TestCase):
	def test_parser_accepts_yolo_and_mcp_server(self):
		parser = interpreter_mod.build_parser()
		# --mcp-server must be last (REMAINDER) so npx -y is not eaten by --yes
		args = parser.parse_args(
			["--yolo", "--mcp-server", "npx", "-y", "@modelcontextprotocol/server-filesystem", "."]
		)
		self.assertTrue(args.yolo)
		self.assertEqual(
			args.mcp_server,
			["npx", "-y", "@modelcontextprotocol/server-filesystem", "."],
		)

	def test_prepare_args_yes_enables_yolo_with_mcp(self):
		parser = interpreter_mod.build_parser()
		args = parser.parse_args(["--yes", "--cli", "-m", "local-model", "--mcp-server", "echo", "hi"])
		args = interpreter_mod.prepare_args(
			args, ["interpreter.py", "--yes", "--cli", "-m", "local-model", "--mcp-server", "echo", "hi"]
		)
		self.assertTrue(args.yolo)
		self.assertTrue(args.cli)
		self.assertFalse(args.tui)
		self.assertEqual(args.mcp_server, ["echo", "hi"])


if __name__ == "__main__":
	unittest.main()
