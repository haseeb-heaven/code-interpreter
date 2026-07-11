"""Unit tests for markdown/code display helpers."""

from __future__ import annotations

import io
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libs.markdown_code import display_code, display_code_stream, display_markdown_message


class TestDisplayMarkdownMessage(unittest.TestCase):
	@patch("libs.markdown_code.rich_print")
	def test_blank_and_rule_and_text(self, rich_print_mock):
		with patch("builtins.print") as print_mock:
			display_markdown_message("hello\n\n---\nworld")
		self.assertTrue(print_mock.called or rich_print_mock.called)
		self.assertGreaterEqual(rich_print_mock.call_count, 2)

	@patch("libs.markdown_code.rich_print")
	def test_blockquote_single_line_adds_blank(self, _rich_print_mock):
		with patch("builtins.print") as print_mock:
			display_markdown_message("> tip")
		print_mock.assert_called()


class TestDisplayCode(unittest.TestCase):
	@patch("libs.markdown_code.rich_print")
	def test_displays_python_syntax(self, rich_print_mock):
		display_code("print(1)", language="python")
		rich_print_mock.assert_called_once()

	@patch("libs.markdown_code.rich_print")
	def test_none_is_noop(self, rich_print_mock):
		display_code(None)
		rich_print_mock.assert_not_called()

	@patch("libs.markdown_code.Syntax", side_effect=RuntimeError("boom"))
	def test_exception_prints_fallback(self, _syntax_mock):
		with patch("builtins.print") as print_mock:
			display_code("x = 1")
		self.assertTrue(any("error" in str(c).lower() for c in print_mock.call_args_list))


class TestDisplayCodeStream(unittest.TestCase):
	@patch("libs.markdown_code.time.sleep", return_value=None)
	@patch("libs.markdown_code.Console")
	def test_stream_prints_tokens(self, console_cls, _sleep):
		console = MagicMock()
		console.export_text.return_value = "print(1)\n"
		console_cls.return_value = console
		tokens = [
			SimpleNamespace(token=SimpleNamespace(text="print")),
			SimpleNamespace(token=SimpleNamespace(text="(1)")),
			SimpleNamespace(token=SimpleNamespace(text="\n")),
		]
		out = display_code_stream(tokens)
		self.assertEqual(out, "print(1)")
		self.assertTrue(console.print.called)


if __name__ == "__main__":
	unittest.main()
