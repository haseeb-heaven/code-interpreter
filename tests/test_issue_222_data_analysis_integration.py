# -*- coding: utf-8 -*-
"""Integration tests for Issue #222 data analysis CLI / REPL."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class TestEdaCliIntegration(unittest.TestCase):
	def test_eda_flag_prints_summary_then_exits(self):
		with tempfile.TemporaryDirectory() as tmp:
			csv_path = Path(tmp) / "sales.csv"
			csv_path.write_text("customer,revenue\nA,10\nB,20\nC,30\n", encoding="utf-8")
			env = os.environ.copy()
			env.pop("INTERPRETER_YES", None)
			env.pop("CI", None)
			env["CODE_INTERPRETER_HOME"] = tmp
			proc = subprocess.run(
				[
					PYTHON,
					str(ROOT / "interpreter.py"),
					"--cli",
					"--eda",
					str(csv_path),
					"-m",
					"local-model",
					"--output-format",
					"plain",
					"--no-color",
				],
				cwd=str(ROOT),
				input="/templates data\n/export csv\n/exit\n",
				capture_output=True,
				text=True,
				timeout=120,
				env=env,
			)
			combined = proc.stdout + proc.stderr
			self.assertNotIn("openai_api_key=", combined.lower())
			self.assertIn("Rows:", combined)
			self.assertIn("Data Analysis Templates", combined)
			self.assertIn("Exported", combined)

	def test_clean_and_sql_repl(self):
		with tempfile.TemporaryDirectory() as tmp:
			csv_path = Path(tmp) / "t.csv"
			csv_path.write_text("n,label\n1,a\n1,a\n2, b \n", encoding="utf-8")
			env = os.environ.copy()
			env.pop("INTERPRETER_YES", None)
			env.pop("CI", None)
			env["CODE_INTERPRETER_HOME"] = tmp
			script = f"/file {csv_path}\n/clean dupes\n/sql SELECT * FROM data\n/exit\n"
			proc = subprocess.run(
				[
					PYTHON,
					str(ROOT / "interpreter.py"),
					"--cli",
					"-m",
					"local-model",
					"--output-format",
					"plain",
					"--no-color",
				],
				cwd=str(ROOT),
				input=script,
				capture_output=True,
				text=True,
				timeout=120,
				env=env,
			)
			combined = proc.stdout + proc.stderr
			self.assertIn("Attached", combined)
			self.assertIn("duplicate", combined.lower())
			self.assertIn("SQL via", combined)


if __name__ == "__main__":
	unittest.main()
