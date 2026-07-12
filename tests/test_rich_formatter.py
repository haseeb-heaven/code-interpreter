# -*- coding: utf-8 -*-
"""Unit tests for libs.output.rich_formatter."""

from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

import pandas as pd

from libs.output.rich_formatter import (
	_fmt_cell,
	print_code,
	print_dataframe,
	print_error,
	print_stats,
)


class TestFmtCell(unittest.TestCase):
	def test_float_small(self):
		self.assertEqual(_fmt_cell(1.23456), "1.2346")

	def test_float_large(self):
		self.assertIn("e", _fmt_cell(1e7).lower())

	def test_int(self):
		self.assertEqual(_fmt_cell(1000), "1,000")

	def test_bool_as_str(self):
		self.assertEqual(_fmt_cell(True), "True")

	def test_str(self):
		self.assertEqual(_fmt_cell("hi"), "hi")

	def test_exception_fallback(self):
		class Boom:
			def __str__(self):
				raise RuntimeError("nope")

			def __format__(self, spec):
				raise RuntimeError("nope")

		# float/int branches skipped; str() fails → outer except returns str(v)
		# which may also fail — ensure function still returns something
		with patch("libs.output.rich_formatter.isinstance", side_effect=RuntimeError("x")):
			self.assertIsInstance(_fmt_cell(1.5), str)


class TestPrintHelpers(unittest.TestCase):
	def test_print_dataframe_with_console(self):
		df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
		console = MagicMock()
		print_dataframe(df, title="T", max_rows=1, console=console)
		self.assertTrue(console.print.called)

	def test_print_dataframe_fallback(self):
		df = pd.DataFrame({"n": list(range(5))})
		with patch("rich.console.Console", side_effect=ImportError("no rich")):
			with patch("builtins.print") as mocked:
				print_dataframe(df, max_rows=2)
				self.assertTrue(mocked.called)

	def test_print_stats_rich(self):
		console = MagicMock()
		print_stats({"acc": 0.9}, console=console)
		self.assertTrue(console.print.called)

	def test_print_stats_fallback(self):
		with patch("rich.console.Console", side_effect=Exception("boom")):
			with patch("builtins.print") as mocked:
				print_stats({"k": "v"})
				mocked.assert_called()

	def test_print_code_rich(self):
		console = MagicMock()
		print_code("print(1)", language="python", console=console)
		self.assertTrue(console.print.called)

	def test_print_code_fallback(self):
		with patch("rich.console.Console", side_effect=Exception("x")):
			with patch("builtins.print") as mocked:
				print_code("x = 1")
				mocked.assert_called_with("x = 1")

	def test_print_error_rich(self):
		console = MagicMock()
		print_error("oops", console=console)
		self.assertTrue(console.print.called)

	def test_print_error_fallback(self):
		with patch("rich.console.Console", side_effect=Exception("x")):
			with patch("builtins.print") as mocked:
				print_error("fail")
				mocked.assert_called_with("fail")

if __name__ == "__main__":
	unittest.main()
