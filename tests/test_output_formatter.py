"""Unit tests for structured output mode (#219)."""

from __future__ import annotations

import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from interpreter import build_parser, prepare_args
from libs.output_formatter import OutputFormat, OutputFormatter


class TestOutputFormatterFormats(unittest.TestCase):
	def test_json_emit_schema_success(self):
		buf = io.StringIO()
		fmt = OutputFormatter(fmt=OutputFormat.JSON, no_color=True, isatty=True)
		fmt.emit(
			result_text="Here is hello world",
			code="print('Hello, World!')",
			execution_output="Hello, World!\n",
			status="success",
			file=buf,
		)
		payload = json.loads(buf.getvalue())
		self.assertEqual(payload["status"], "success")
		self.assertEqual(payload["result"], "Here is hello world")
		self.assertEqual(payload["code"], "print('Hello, World!')")
		self.assertEqual(payload["execution_output"], "Hello, World!\n")
		self.assertNotIn("error", payload)

	def test_json_emit_error_case(self):
		buf = io.StringIO()
		fmt = OutputFormatter(fmt=OutputFormat.JSON, isatty=True)
		fmt.emit(
			result_text="I generated the code but execution failed.",
			code="import nonexistent_module",
			error="ModuleNotFoundError: No module named 'nonexistent_module'",
			status="error",
			file=buf,
		)
		payload = json.loads(buf.getvalue())
		self.assertEqual(payload["status"], "error")
		self.assertIn("nonexistent_module", payload["error"])
		self.assertIn("import nonexistent_module", payload["code"])

	def test_markdown_emit_sections(self):
		buf = io.StringIO()
		fmt = OutputFormatter(fmt=OutputFormat.MARKDOWN, isatty=True)
		fmt.emit(
			result_text="Done",
			code="print(1)",
			execution_output="1",
			language="python",
			file=buf,
		)
		text = buf.getvalue()
		self.assertIn("## Result", text)
		self.assertIn("## Generated Code", text)
		self.assertIn("```python", text)
		self.assertIn("print(1)", text)
		self.assertIn("## Execution Output", text)

	def test_plain_emit_is_noop(self):
		buf = io.StringIO()
		fmt = OutputFormatter(fmt=OutputFormat.PLAIN, isatty=True)
		# plain uses stdout by design; ensure no exception and no structured dump
		fmt.emit(result_text="hello", code="x=1", file=buf)
		self.assertEqual(buf.getvalue(), "")

	def test_strip_ansi_from_json_values(self):
		buf = io.StringIO()
		fmt = OutputFormatter(fmt=OutputFormat.JSON, isatty=True)
		colored = "\x1b[31mred\x1b[0m result"
		fmt.emit(result_text=colored, code="\x1b[32mcode\x1b[0m", file=buf)
		payload = json.loads(buf.getvalue())
		self.assertEqual(payload["result"], "red result")
		self.assertEqual(payload["code"], "code")
		self.assertNotIn("\x1b", payload["result"])


class TestOutputFormatterAutoDetect(unittest.TestCase):
	def test_auto_json_when_non_tty(self):
		args = SimpleNamespace(output_format=None, no_color=False)
		fmt = OutputFormatter.from_args(args, isatty=False)
		self.assertEqual(fmt.fmt, OutputFormat.JSON)
		self.assertTrue(fmt.no_color)
		self.assertTrue(fmt.is_structured)

	def test_auto_plain_when_tty(self):
		args = SimpleNamespace(output_format=None, no_color=False)
		fmt = OutputFormatter.from_args(args, isatty=True)
		self.assertEqual(fmt.fmt, OutputFormat.PLAIN)
		self.assertFalse(fmt.is_structured)

	def test_explicit_plain_overrides_pipe(self):
		args = SimpleNamespace(output_format="plain", no_color=False)
		fmt = OutputFormatter.from_args(args, isatty=False)
		self.assertEqual(fmt.fmt, OutputFormat.PLAIN)
		self.assertFalse(fmt.is_structured)

	def test_explicit_json_on_tty(self):
		args = SimpleNamespace(output_format="json", no_color=False)
		fmt = OutputFormatter.from_args(args, isatty=True)
		self.assertEqual(fmt.fmt, OutputFormat.JSON)
		self.assertTrue(fmt.is_structured)


class TestOutputFormatCliFlags(unittest.TestCase):
	def test_parser_accepts_formats(self):
		parser = build_parser()
		args = parser.parse_args(["--cli", "--output-format", "json", "--no-color"])
		self.assertEqual(args.output_format, "json")
		self.assertTrue(args.no_color)

	def test_prepare_args_disables_stream_for_json(self):
		parser = build_parser()
		args = parser.parse_args(
			["--cli", "--output-format", "json", "-m", "local-model", "--mode", "code"]
		)
		prepared = prepare_args(args, ["interpreter.py", "--cli", "--output-format", "json"])
		self.assertFalse(prepared.stream)
		self.assertTrue(prepared.cli)

	def test_apply_env_suppression_sets_ci(self):
		fmt = OutputFormatter(fmt=OutputFormat.JSON, isatty=True)
		with patch.dict("os.environ", {}, clear=False):
			fmt.apply_env_suppression()
			import os

			self.assertEqual(os.environ.get("CI"), "1")
			self.assertEqual(os.environ.get("NO_COLOR"), "1")


if __name__ == "__main__":
	unittest.main()
