# -*- coding: utf-8 -*-
"""Unit tests for Issue #222 data analysis engine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from libs.data.auto_eda import build_eda_prompt, deterministic_eda_summary
from libs.data.data_cleaner import clean_all, clean_dupes, clean_nulls, clean_whitespace
from libs.data.file_ingestor import FileIngestError, ingest, prompt_context
from libs.data.session_data import DataSession
from libs.data.sql_runner import run_sql_on_df
from libs.data.templates import format_templates
from libs.output.chart_manager import inject_auto_save, list_charts, needs_chart_hook
from libs.output.exporter import export_dataframe
from libs.output.plotly_manager import inject_plotly_helper, plotly_safety_hint, plotly_system_hint


class TestFileIngestor(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name)

	def tearDown(self):
		self.tmp.cleanup()

	def test_ingest_csv_schema_preview(self):
		p = self.root / "s.csv"
		p.write_text("name,score\nA,1\nB,2\n", encoding="utf-8")
		result = ingest(str(p))
		self.assertEqual(result["shape"], (2, 2))
		self.assertIn("name", result["schema"])
		self.assertIn("score", result["preview"])
		ctx = prompt_context(result)
		self.assertIn(str(p.resolve()), ctx)
		self.assertNotIn("api_key", ctx.lower())

	def test_missing_file(self):
		with self.assertRaises(FileIngestError):
			ingest(str(self.root / "nope.csv"))


class TestDataSessionAndClean(unittest.TestCase):
	def test_session_load_and_context(self):
		with tempfile.TemporaryDirectory() as tmp:
			p = Path(tmp) / "d.csv"
			p.write_text("a,b\n1,2\n1,2\n,\n", encoding="utf-8")
			session = DataSession()
			session.load_file(str(p))
			block = session.context_block()
			self.assertIn("Active dataset", block)
			self.assertIn("load:", ",".join(session.history))

	def test_cleaners(self):
		df = pd.DataFrame({"a": [1, 1, None], "b": [" x ", "x", "y"]})
		out, msg = clean_whitespace(df)
		self.assertIn("Stripped", msg)
		out, msg = clean_dupes(out)
		self.assertTrue(len(out) <= len(df))
		out, msg = clean_nulls(out, strategy="zero")
		self.assertEqual(int(out.isnull().sum().sum()), 0)
		out, msg = clean_all(df)
		self.assertIsInstance(out, pd.DataFrame)


class TestEdaSqlExportCharts(unittest.TestCase):
	def test_eda_prompt_and_summary(self):
		df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "a"]})
		summary = deterministic_eda_summary(df)
		self.assertIn("Rows: 3", summary)
		prompt = build_eda_prompt("/tmp/x.csv", {"path": "/tmp/x.csv", "schema": "x:int", "preview": "1", "shape": (3, 2), "null_summary": "none", "numeric_summary": "ok"})
		self.assertIn("exploratory", prompt.lower())
		self.assertIn("/tmp/x.csv", prompt)

	def test_sql_select(self):
		df = pd.DataFrame({"n": [1, 2, 3]})
		result, engine = run_sql_on_df(df, "SELECT * FROM data WHERE n > 1")
		self.assertEqual(len(result), 2)
		self.assertIn(engine, ("duckdb", "sqlite3"))

	def test_export_csv_and_report(self):
		with tempfile.TemporaryDirectory() as tmp:
			home = Path(tmp)
			df = pd.DataFrame({"a": [1, 2]})
			path = export_dataframe(df, "csv", home=home)
			self.assertTrue(path.exists())
			report = export_dataframe(df, "report", home=home, charts=[])
			self.assertTrue(report.exists())
			self.assertIn("Analysis Report", report.read_text(encoding="utf-8"))

	def test_chart_hooks(self):
		code = "import matplotlib.pyplot as plt\nplt.plot([1,2])\nplt.show()\n"
		self.assertTrue(needs_chart_hook(code))
		injected = inject_auto_save(code)
		self.assertIn("_ci_auto_show", injected)
		plotly = inject_plotly_helper("import plotly.express as px\nfig = px.scatter(x=[1], y=[2])\n")
		self.assertIn("_ci_write_html", plotly)
		self.assertIn("plotly", plotly_system_hint().lower())

	def test_plotly_safety_hint_warns_against_write_image(self):
		hint = plotly_safety_hint().lower()
		self.assertIn("write_html", hint)
		self.assertIn("write_image", hint)
		self.assertIn("kaleido", hint)

	def test_templates(self):
		text = format_templates("data")
		self.assertIn("Data Analysis Templates", text)
		self.assertIn("analyze", text.lower())


class TestCliFlags222(unittest.TestCase):
	def test_parser_eda_and_interactive(self):
		import interpreter as mod

		parser = mod.build_parser()
		args = parser.parse_args(["--eda", "sales.csv", "--interactive-charts", "--cli"])
		self.assertEqual(args.eda, "sales.csv")
		self.assertTrue(args.interactive_charts)

	def test_help_mentions_eda(self):
		import interpreter as mod
		import io
		from contextlib import redirect_stdout

		buf = io.StringIO()
		with redirect_stdout(buf):
			try:
				mod.build_parser().parse_args(["--help"])
			except SystemExit:
				pass
		out = buf.getvalue()
		self.assertIn("--eda", out)
		self.assertIn("--interactive-charts", out)


if __name__ == "__main__":
	unittest.main()
