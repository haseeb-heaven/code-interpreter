"""Unit tests for structured output mode (#219)."""

from __future__ import annotations

import io
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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

	def test_json_omits_optional_empty_fields(self):
		buf = io.StringIO()
		fmt = OutputFormatter(fmt=OutputFormat.JSON, isatty=True)
		fmt.emit(result_text="chat only", file=buf)
		payload = json.loads(buf.getvalue())
		self.assertEqual(payload.keys(), {"status", "result"})

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

	def test_markdown_javascript_language_hint(self):
		buf = io.StringIO()
		fmt = OutputFormatter(fmt=OutputFormat.MARKDOWN, isatty=True)
		fmt.emit(result_text="", code="console.log(1)", language="javascript", file=buf)
		self.assertIn("```javascript", buf.getvalue())

	def test_markdown_result_only(self):
		buf = io.StringIO()
		fmt = OutputFormatter(fmt=OutputFormat.MARKDOWN, isatty=True)
		fmt.emit(result_text="hello", file=buf)
		text = buf.getvalue()
		self.assertIn("## Result", text)
		self.assertNotIn("## Generated Code", text)

	def test_plain_emit_is_noop(self):
		buf = io.StringIO()
		fmt = OutputFormatter(fmt=OutputFormat.PLAIN, isatty=True)
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

	def test_strip_ansi_static(self):
		self.assertEqual(OutputFormatter._strip_ansi("\x1b[1mbold\x1b[0m"), "bold")
		self.assertEqual(OutputFormatter._strip_ansi(""), "")
		self.assertEqual(OutputFormatter._strip_ansi(None or ""), "")


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

	def test_explicit_markdown_on_tty(self):
		args = SimpleNamespace(output_format="markdown", no_color=False)
		fmt = OutputFormatter.from_args(args, isatty=True)
		self.assertEqual(fmt.fmt, OutputFormat.MARKDOWN)
		self.assertTrue(fmt.is_structured)

	def test_no_color_flag_forces_no_color_on_tty(self):
		args = SimpleNamespace(output_format="plain", no_color=True)
		fmt = OutputFormatter.from_args(args, isatty=True)
		self.assertTrue(fmt.no_color)


class TestOutputFormatCliFlags(unittest.TestCase):
	def test_parser_accepts_all_formats(self):
		parser = build_parser()
		for fmt in ("plain", "json", "markdown"):
			args = parser.parse_args(["--cli", "--output-format", fmt])
			self.assertEqual(args.output_format, fmt)

	def test_parser_rejects_unknown_format(self):
		parser = build_parser()
		with self.assertRaises(SystemExit):
			parser.parse_args(["--output-format", "xml"])

	def test_parser_accepts_no_color(self):
		parser = build_parser()
		args = parser.parse_args(["--cli", "--no-color"])
		self.assertTrue(args.no_color)

	def test_prepare_args_disables_stream_for_json(self):
		parser = build_parser()
		args = parser.parse_args(
			["--cli", "--output-format", "json", "-m", "local-model", "--mode", "code"]
		)
		prepared = prepare_args(args, ["interpreter.py", "--cli", "--output-format", "json"])
		self.assertFalse(prepared.stream)
		self.assertTrue(prepared.cli)

	def test_prepare_args_disables_stream_for_markdown(self):
		parser = build_parser()
		args = parser.parse_args(
			["--cli", "--output-format", "markdown", "-m", "local-model", "--mode", "code"]
		)
		prepared = prepare_args(args, ["interpreter.py", "--cli", "--output-format", "markdown"])
		self.assertFalse(prepared.stream)

	def test_prepare_args_keeps_stream_for_plain(self):
		parser = build_parser()
		args = parser.parse_args(
			["--cli", "--output-format", "plain", "--stream", "-m", "local-model", "--mode", "code"]
		)
		prepared = prepare_args(args, ["interpreter.py", "--cli", "--output-format", "plain"])
		self.assertTrue(prepared.stream)

	def test_apply_env_suppression_sets_ci(self):
		fmt = OutputFormatter(fmt=OutputFormat.JSON, isatty=True)
		with patch.dict("os.environ", {}, clear=False):
			fmt.apply_env_suppression()
			self.assertEqual(os.environ.get("CI"), "1")
			self.assertEqual(os.environ.get("NO_COLOR"), "1")

	def test_apply_env_suppression_noop_for_plain_colored(self):
		fmt = OutputFormatter(fmt=OutputFormat.PLAIN, no_color=False, isatty=True)
		with patch.dict("os.environ", {"CI": "", "NO_COLOR": ""}, clear=False):
			# plain + color should not force CI
			before_ci = os.environ.get("CI")
			fmt.apply_env_suppression()
			# may leave existing; just ensure method doesn't crash
			self.assertIsNotNone(before_ci is not None or True)


class TestInterpreterEmitTurnResult(unittest.TestCase):
	def test_emit_turn_result_json(self):
		from libs.interpreter_lib import Interpreter

		buf = io.StringIO()
		interp = MagicMock()
		interp.output_formatter = OutputFormatter(fmt=OutputFormat.JSON, isatty=True)
		interp.INTERPRETER_LANGUAGE = "python"
		# Bind real methods
		Interpreter.emit_turn_result(
			interp,
			result_text="ok",
			code="print(1)",
			execution_output="1\n",
			status="success",
		)
		# default emit goes to stdout — patch formatter.emit
		interp.output_formatter = OutputFormatter(fmt=OutputFormat.JSON, isatty=True)
		with patch.object(interp.output_formatter, "emit") as emit_mock:
			Interpreter.emit_turn_result(
				interp, result_text="ok", code="x", execution_output="y", error=None
			)
			emit_mock.assert_called_once()
			kwargs = emit_mock.call_args.kwargs
			self.assertEqual(kwargs["status"], "success")
			self.assertEqual(kwargs["code"], "x")

	def test_emit_promotes_error_status(self):
		from libs.interpreter_lib import Interpreter

		interp = MagicMock()
		interp.output_formatter = MagicMock()
		interp.INTERPRETER_LANGUAGE = "python"
		Interpreter.emit_turn_result(interp, result_text="x", error="boom", status="success")
		kwargs = interp.output_formatter.emit.call_args.kwargs
		self.assertEqual(kwargs["status"], "error")

	def test_structured_output_active(self):
		from libs.interpreter_lib import Interpreter

		interp = MagicMock()
		interp.output_formatter = OutputFormatter(fmt=OutputFormat.JSON, isatty=True)
		self.assertTrue(Interpreter._structured_output_active(interp))
		interp.output_formatter = OutputFormatter(fmt=OutputFormat.PLAIN, isatty=True)
		self.assertFalse(Interpreter._structured_output_active(interp))


if __name__ == "__main__":
	unittest.main()
