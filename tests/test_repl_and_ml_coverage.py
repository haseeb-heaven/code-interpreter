# -*- coding: utf-8 -*-
"""Unit tests for libs.data.repl_data_commands and ml_shortcuts."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

from libs.data.ml_shortcuts import run_ml_shortcut
from libs.data.repl_data_commands import (
	check_rscript_available,
	ensure_data_session,
	handle_data_repl_command,
)
from libs.data.session_data import DataSession


class TestEnsureDataSession(unittest.TestCase):
	def test_creates_when_missing(self):
		interp = SimpleNamespace()
		session = ensure_data_session(interp)
		self.assertIsInstance(session, DataSession)
		self.assertIs(interp.data_session, session)

	def test_reuses_existing(self):
		existing = DataSession()
		interp = SimpleNamespace(data_session=existing)
		self.assertIs(ensure_data_session(interp), existing)


class TestHandleDataReplCommands(unittest.TestCase):
	def setUp(self):
		self.msgs = []
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name)
		csv_path = self.root / "data.csv"
		csv_path.write_text("x,y,label\n1,2,a\n3,4,b\n5,6,a\n7,8,b\n9,10,a\n", encoding="utf-8")
		self.csv_path = str(csv_path)
		self.session = DataSession()
		self.session.load_file(self.csv_path)
		self.interp = SimpleNamespace(
			data_session=self.session,
			_pending_eda_prompt=None,
			_pending_sql_prompt=None,
			_last_full_output=None,
		)

	def tearDown(self):
		self.tmp.cleanup()

	def _display(self, msg):
		self.msgs.append(msg)

	def test_non_command_returns_false(self):
		self.assertFalse(handle_data_repl_command(self.interp, "hello", self._display))

	def test_eda_usage_without_path(self):
		self.session.active_file = None
		self.session.df = None
		ok = handle_data_repl_command(self.interp, "/eda", self._display)
		self.assertTrue(ok)
		self.assertTrue(any("Usage" in m for m in self.msgs))

	def test_eda_with_path(self):
		ok = handle_data_repl_command(self.interp, f"/eda {self.csv_path}", self._display)
		self.assertTrue(ok)
		self.assertIsNotNone(self.interp._pending_eda_prompt)
		self.assertTrue(any("EDA" in m for m in self.msgs))

	def test_charts_list_empty(self):
		with patch("libs.output.chart_manager.list_charts", return_value=[]), patch(
			"libs.output.plotly_manager.list_plotly_charts", return_value=[]
		):
			ok = handle_data_repl_command(self.interp, "/charts", self._display)
		self.assertTrue(ok)
		self.assertTrue(any("No charts" in m for m in self.msgs))

	def test_charts_list_with_files(self):
		png = self.root / "c.png"
		png.write_bytes(b"x")
		with patch("libs.output.chart_manager.list_charts", return_value=[png]), patch(
			"libs.output.plotly_manager.list_plotly_charts", return_value=[]
		):
			ok = handle_data_repl_command(self.interp, "/charts list", self._display)
		self.assertTrue(ok)
		self.assertTrue(any("Saved charts" in m for m in self.msgs))

	def test_charts_dir(self):
		with patch("libs.output.chart_manager.chart_dir", return_value=self.root), patch(
			"libs.output.chart_manager.open_file", return_value=True
		):
			ok = handle_data_repl_command(self.interp, "/charts dir", self._display)
		self.assertTrue(ok)

	def test_charts_open(self):
		png = self.root / "c.png"
		png.write_bytes(b"x")
		with patch("libs.output.chart_manager.list_charts", return_value=[png]), patch(
			"libs.output.chart_manager.open_file", return_value=True
		) as opener:
			ok = handle_data_repl_command(self.interp, "/charts open 1", self._display)
		self.assertTrue(ok)
		opener.assert_called()

	def test_charts_open_usage_and_range(self):
		with patch("libs.output.chart_manager.list_charts", return_value=[]):
			handle_data_repl_command(self.interp, "/charts open", self._display)
			handle_data_repl_command(self.interp, "/charts open 9", self._display)
		self.assertTrue(any("Usage" in m or "out of range" in m for m in self.msgs))

	def test_charts_unknown_sub(self):
		handle_data_repl_command(self.interp, "/charts weird", self._display)
		self.assertTrue(any("Usage" in m for m in self.msgs))

	def test_export_without_df(self):
		self.session.df = None
		ok = handle_data_repl_command(self.interp, "/export csv", self._display)
		self.assertTrue(ok)
		self.assertTrue(any("No active dataset" in m for m in self.msgs))

	def test_export_csv(self):
		with patch(
			"libs.output.exporter.export_dataframe",
			return_value=self.root / "out.csv",
		), patch("libs.output.chart_manager.list_charts", return_value=[]):
			ok = handle_data_repl_command(self.interp, "/export csv", self._display)
		self.assertTrue(ok)
		self.assertTrue(any("Exported" in m for m in self.msgs))

	def test_clean_ops(self):
		for cmd in (
			"/clean nulls median",
			"/clean dupes",
			"/clean types",
			"/clean dates",
			"/clean whitespace",
			"/clean all",
		):
			self.msgs.clear()
			self.session.load_file(self.csv_path)
			ok = handle_data_repl_command(self.interp, cmd, self._display)
			self.assertTrue(ok, cmd)

	def test_clean_bad_op(self):
		handle_data_repl_command(self.interp, "/clean nope", self._display)
		self.assertTrue(any("Usage" in m for m in self.msgs))

	def test_clean_no_df(self):
		self.session.df = None
		handle_data_repl_command(self.interp, "/clean all", self._display)
		self.assertTrue(any("No active dataset" in m for m in self.msgs))

	def test_sql_usage_and_select(self):
		handle_data_repl_command(self.interp, "/sql", self._display)
		self.msgs.clear()
		ok = handle_data_repl_command(
			self.interp, '/sql SELECT * FROM data WHERE x > 1', self._display
		)
		self.assertTrue(ok)
		self.assertTrue(any("SQL via" in m for m in self.msgs))

	def test_sql_nl_prompt(self):
		# Avoid SQL-looking prefixes (select/with/show/describe) so NL path is used.
		ok = handle_data_repl_command(
			self.interp, "/sql how many rows have x greater than one", self._display
		)
		self.assertTrue(ok)
		self.assertIsNotNone(self.interp._pending_sql_prompt)

	def test_sql_no_df(self):
		self.session.df = None
		handle_data_repl_command(self.interp, "/sql SELECT 1", self._display)
		self.assertTrue(any("No active dataset" in m for m in self.msgs))

	def test_templates(self):
		ok = handle_data_repl_command(self.interp, "/templates data", self._display)
		self.assertTrue(ok)
		self.assertTrue(self.msgs)

	def test_chart_style(self):
		handle_data_repl_command(self.interp, "/chart-style", self._display)
		handle_data_repl_command(self.interp, "/chart-style plotly", self._display)
		self.assertEqual(self.session.chart_style, "plotly")
		handle_data_repl_command(self.interp, "/chart-style bad", self._display)

	def test_notebook_save(self):
		self.session.record_cell("markdown", "hello")
		with patch(
			"libs.output.notebook_exporter.export_to_notebook",
			return_value=str(self.root / "n.ipynb"),
		):
			ok = handle_data_repl_command(self.interp, "/notebook save", self._display)
		self.assertTrue(ok)

	def test_notebook_open(self):
		with patch(
			"libs.output.notebook_exporter.export_to_notebook",
			return_value=str(self.root / "n.ipynb"),
		), patch("libs.output.chart_manager.open_file", return_value=True):
			ok = handle_data_repl_command(self.interp, "/notebook open", self._display)
		self.assertTrue(ok)

	def test_ml_cluster(self):
		ok = handle_data_repl_command(self.interp, "/ml cluster 2", self._display)
		self.assertTrue(ok)

	def test_ml_classify(self):
		ok = handle_data_repl_command(self.interp, "/ml classify label", self._display)
		self.assertTrue(ok)

	def test_ml_usage_and_no_df(self):
		handle_data_repl_command(self.interp, "/ml", self._display)
		self.session.df = None
		handle_data_repl_command(self.interp, "/ml cluster", self._display)

	def test_output_full(self):
		handle_data_repl_command(self.interp, "/output", self._display)
		self.interp._last_full_output = "hello world"
		ok = handle_data_repl_command(self.interp, "/output full", self._display)
		self.assertTrue(ok)
		self.assertTrue(any("Full output written" in m for m in self.msgs))

	def test_exception_path(self):
		with patch(
			"libs.data.repl_data_commands._cmd_templates",
			side_effect=RuntimeError("boom"),
		):
			ok = handle_data_repl_command(self.interp, "/templates", self._display)
		self.assertTrue(ok)
		self.assertTrue(any("Error:" in m for m in self.msgs))

	def test_check_rscript(self):
		with patch("libs.data.repl_data_commands.shutil.which", return_value="/bin/Rscript"):
			self.assertEqual(check_rscript_available(), "/bin/Rscript")
		with patch("libs.data.repl_data_commands.shutil.which", return_value=None):
			self.assertIsNone(check_rscript_available())


class TestMlShortcuts(unittest.TestCase):
	def test_empty_df(self):
		with self.assertRaises(ValueError):
			run_ml_shortcut(pd.DataFrame(), "cluster")

	def test_cluster(self):
		df = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6], "b": [6, 5, 4, 3, 2, 1]})
		summary, metrics = run_ml_shortcut(df, "cluster", n_clusters=2)
		self.assertIn("KMeans", summary)
		self.assertIn("n_clusters", metrics)

	def test_cluster_no_numeric(self):
		df = pd.DataFrame({"a": ["x", "y"]})
		with self.assertRaises(ValueError):
			run_ml_shortcut(df, "cluster")

	def test_classify(self):
		df = pd.DataFrame(
			{
				"f1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
				"f2": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
				"y": ["a", "b", "a", "b", "a", "b", "a", "b", "a", "b"],
			}
		)
		summary, metrics = run_ml_shortcut(df, "classify", target="y")
		self.assertIn("accuracy", metrics)
		self.assertIn("Classifier", summary)

	def test_regress(self):
		df = pd.DataFrame(
			{
				"f1": list(range(10)),
				"f2": list(range(10, 20)),
				"y": [i * 2 for i in range(10)],
			}
		)
		summary, metrics = run_ml_shortcut(df, "regress", target="y")
		self.assertIn("r2", metrics)
		self.assertIn("Regressor", summary)

	def test_missing_target(self):
		df = pd.DataFrame({"a": [1, 2, 3]})
		with self.assertRaises(ValueError):
			run_ml_shortcut(df, "classify", target=None)

	def test_bad_kind(self):
		df = pd.DataFrame({"a": [1, 2, 3], "b": [1, 2, 3]})
		with self.assertRaises(ValueError):
			run_ml_shortcut(df, "weird", target="b")


class TestFileIngestorExtra(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name)

	def tearDown(self):
		self.tmp.cleanup()

	def test_json_and_tsv_and_text(self):
		from libs.data.file_ingestor import ingest

		json_path = self.root / "d.json"
		json_path.write_text('[{"a":1},{"a":2}]', encoding="utf-8")
		r = ingest(str(json_path), max_rows=1)
		self.assertEqual(r["shape"][0], 1)

		tsv = self.root / "d.tsv"
		tsv.write_text("a\tb\n1\t2\n", encoding="utf-8")
		self.assertEqual(ingest(str(tsv))["file_type"], ".tsv")

		txt = self.root / "n.log"
		txt.write_text("line1\nline2\n", encoding="utf-8")
		self.assertIn("line", ingest(str(txt))["schema"])

	def test_sqlite(self):
		from libs.data.file_ingestor import ingest

		db = self.root / "t.db"
		con = sqlite3.connect(str(db))
		con.execute("CREATE TABLE t (a INTEGER)")
		con.execute("INSERT INTO t VALUES (1)")
		con.commit()
		con.close()
		r = ingest(str(db))
		self.assertEqual(r["file_type"], ".db")
		self.assertEqual(r["shape"][0], 1)

	def test_unsupported(self):
		from libs.data.file_ingestor import FileIngestError, ingest

		p = self.root / "x.bin"
		p.write_bytes(b"\x00\x01")
		with self.assertRaises(FileIngestError):
			ingest(str(p))

	def test_ndjson(self):
		from libs.data.file_ingestor import ingest

		p = self.root / "nd.json"
		p.write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
		r = ingest(str(p))
		self.assertEqual(r["shape"][0], 2)


class TestChartExporterExtra(unittest.TestCase):
	def test_chart_dir_list_save_open(self):
		from libs.output.chart_manager import (
			chart_dir,
			inject_auto_save,
			list_charts,
			open_file,
			save_current_figure,
		)

		with tempfile.TemporaryDirectory() as tmp:
			home = Path(tmp)
			d = chart_dir(home)
			self.assertTrue(d.is_dir())
			import matplotlib

			matplotlib.use("Agg")
			import matplotlib.pyplot as plt

			plt.plot([1, 2])
			path = save_current_figure(home=home)
			self.assertTrue(path.is_file())
			self.assertTrue(list_charts(5, home=home))
			with patch("libs.output.chart_manager.os.startfile", create=True), patch(
				"libs.output.chart_manager.sys.platform", "win32"
			):
				self.assertTrue(open_file(path))
			code = inject_auto_save("import matplotlib.pyplot as plt\nplt.show()\n")
			self.assertIn("_ci_auto_show", code)
			self.assertEqual(inject_auto_save("print(1)"), "print(1)")

	def test_export_formats(self):
		from libs.output.exporter import export_dataframe

		df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
		with tempfile.TemporaryDirectory() as tmp:
			home = Path(tmp)
			for fmt in ("csv", "json", "markdown", "html", "excel", "report"):
				path = export_dataframe(df, fmt, home=home, stem=f"t_{fmt}")
				self.assertTrue(path.exists(), fmt)
			with self.assertRaises(ValueError):
				export_dataframe(None, "csv", home=home)
			with self.assertRaises(ValueError):
				export_dataframe(df, "nope", home=home)
			# PDF if reportlab present
			try:
				pdf = export_dataframe(df, "pdf", home=home, stem="t_pdf", summary_text="sum")
				self.assertTrue(pdf.exists())
			except ImportError:
				pass


if __name__ == "__main__":
	unittest.main()
