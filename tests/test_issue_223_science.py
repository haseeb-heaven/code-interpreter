# -*- coding: utf-8 -*-
"""Unit + integration tests for Issue #223 scientific computing features."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


class TestSciencePrompt(unittest.TestCase):
	def test_auto_detect_and_force(self):
		from libs.prompts.science_prompt import looks_like_science_task, science_prompt_block

		self.assertTrue(looks_like_science_task("run a t-test on these groups"))
		self.assertFalse(looks_like_science_task("rename my pdfs"))
		self.assertIn("scipy.stats", science_prompt_block(force=True))
		self.assertEqual(science_prompt_block(task="hello"), "")


class TestNotebookAndThemes(unittest.TestCase):
	def test_notebook_export(self):
		from libs.output.notebook_exporter import export_to_notebook

		with tempfile.TemporaryDirectory() as tmp:
			path = export_to_notebook(
				[{"type": "code", "source": "print(1)", "output": "1\n"}],
				output_path=str(Path(tmp) / "s.ipynb"),
				title="Test",
			)
			data = json.loads(Path(path).read_text(encoding="utf-8"))
			self.assertEqual(data["nbformat"], 4)
			self.assertGreaterEqual(len(data["cells"]), 2)

	def test_plot_theme_inject(self):
		from libs.output.plot_themes import inject_plot_theme

		code = "import matplotlib.pyplot as plt\nplt.plot([1,2])\n"
		out = inject_plot_theme(code, "paper")
		self.assertIn("_ci_plot_theme=paper", out)
		self.assertIn("figure.dpi", out)


class TestTruncationAndAutoInstall(unittest.TestCase):
	def test_format_output_truncates_lines(self):
		from libs.execution.output_truncation import format_output

		raw = "\n".join(f"line{i}" for i in range(100))
		out = format_output(raw, max_lines=50)
		self.assertIn("truncated", out)
		self.assertIn("line0", out)
		self.assertIn("line99", out)

	def test_auto_install_skips_stdlib(self):
		from libs.execution.auto_install import auto_install_missing

		installed = auto_install_missing("import os\nimport json\n", enabled=True)
		self.assertEqual(installed, [])


class TestMlAndPdfAndGlob(unittest.TestCase):
	def test_ml_cluster(self):
		from libs.data.ml_shortcuts import run_ml_shortcut

		df = pd.DataFrame({"x": [1, 2, 3, 10, 11, 12], "y": [1, 1, 2, 10, 11, 12]})
		summary, metrics = run_ml_shortcut(df, "cluster", n_clusters=2)
		self.assertIn("KMeans", summary)
		self.assertIn("n_clusters", metrics)

	def test_pdf_export(self):
		from libs.output.exporter import export_dataframe

		with tempfile.TemporaryDirectory() as tmp:
			path = export_dataframe(
				pd.DataFrame({"a": [1, 2]}),
				"pdf",
				home=Path(tmp),
				summary_text="hello",
			)
			self.assertTrue(path.exists())
			self.assertEqual(path.suffix, ".pdf")

	def test_glob_normalize_paths(self):
		from libs.context.file_context import normalize_paths

		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			(root / "a.csv").write_text("x\n1\n", encoding="utf-8")
			(root / "b.csv").write_text("x\n2\n", encoding="utf-8")
			paths = normalize_paths([str(root / "*.csv")])
			self.assertEqual(len(paths), 2)


class TestCliFlags223(unittest.TestCase):
	def test_parser_science_flags(self):
		import interpreter as mod

		args = mod.build_parser().parse_args(
			["--science", "--plot-theme", "paper", "--report", "--cli"]
		)
		self.assertTrue(args.science)
		self.assertEqual(args.plot_theme, "paper")
		self.assertTrue(args.report)


class TestNotebookReplIntegration(unittest.TestCase):
	def test_notebook_command_after_file(self):
		import os
		import subprocess
		import sys

		root = Path(__file__).resolve().parents[1]
		with tempfile.TemporaryDirectory() as tmp:
			csv_path = Path(tmp) / "d.csv"
			csv_path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
			nb_path = Path(tmp) / "out.ipynb"
			env = os.environ.copy()
			env.pop("INTERPRETER_YES", None)
			env.pop("CI", None)
			env["CODE_INTERPRETER_HOME"] = tmp
			script = f"/file {csv_path}\n/notebook save {nb_path}\n/exit\n"
			proc = subprocess.run(
				[
					sys.executable,
					str(root / "interpreter.py"),
					"--cli",
					"-m",
					"local-model",
					"--output-format",
					"plain",
					"--no-color",
				],
				cwd=str(root),
				input=script,
				capture_output=True,
				text=True,
				timeout=120,
				env=env,
			)
			combined = proc.stdout + proc.stderr
			self.assertIn("Notebook saved", combined)
			self.assertTrue(nb_path.exists())
			self.assertNotIn("openai_api_key=", combined.lower())


if __name__ == "__main__":
	unittest.main()
