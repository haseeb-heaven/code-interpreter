"""Unit tests for CodeInterpreter extract/save helpers and safe execute paths."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from libs.code_interpreter import (
	CodeInterpreter,
	_is_python_code,
	_strip_leading_fence_language_line,
)


class TestCodeInterpreterHelpers(unittest.TestCase):
	def test_is_python_code(self):
		self.assertTrue(_is_python_code("print(1)"))
		self.assertFalse(_is_python_code("for x in *.txt; do echo $x; done"))

	def test_strip_leading_fence_language_line(self):
		self.assertEqual(_strip_leading_fence_language_line("python\nprint(1)"), "print(1)")
		self.assertEqual(_strip_leading_fence_language_line("print(1)"), "print(1)")
		self.assertEqual(_strip_leading_fence_language_line("python"), "")

	def test_extract_code_fenced(self):
		ci = CodeInterpreter()
		code = ci.extract_code("Here:\n```python\nprint(42)\n```\n")
		self.assertEqual(code.strip(), "print(42)")

	def test_extract_code_no_fence(self):
		ci = CodeInterpreter()
		self.assertEqual(ci.extract_code("print(1)"), "print(1)")

	def test_extract_code_none(self):
		ci = CodeInterpreter()
		with patch("libs.code_interpreter.display_markdown_message"):
			self.assertIsNone(ci.extract_code(None))

	def test_save_code(self):
		ci = CodeInterpreter()
		with tempfile.TemporaryDirectory() as tmp:
			path = Path(tmp) / "out.py"
			ci.save_code(str(path), "print(1)")
			self.assertEqual(path.read_text(encoding="utf-8"), "print(1)")

	def test_execute_code_empty(self):
		ci = CodeInterpreter()
		ci.UNSAFE_EXECUTION = True
		out, err = ci.execute_code("  ", "python", force_execute=True)
		self.assertIsNone(out)
		self.assertIn("empty", err.lower())

	def test_execute_code_force_python(self):
		ci = CodeInterpreter()
		ci.UNSAFE_EXECUTION = True
		out, err = ci.execute_code("print('ci-ok')", "python", force_execute=True)
		self.assertIn("ci-ok", out or "")
		self.assertFalse(err)

	def test_execute_code_normalizes_os_language(self):
		ci = CodeInterpreter()
		ci.UNSAFE_EXECUTION = True
		out, err = ci.execute_code("print('win')", "windows", force_execute=True)
		self.assertIn("win", out or "")


if __name__ == "__main__":
	unittest.main()
