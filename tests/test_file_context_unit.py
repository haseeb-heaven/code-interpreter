# -*- coding: utf-8 -*-
"""Unit tests for local file context builder (Issue #221)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from libs.context.file_context import (
	build_file_context,
	inject_file_context,
	normalize_paths,
)


class TestFileContext(unittest.TestCase):
	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.root = Path(self._tmpdir.name)

	def tearDown(self):
		self._tmpdir.cleanup()

	def test_normalize_paths_dedupes(self):
		self.assertEqual(normalize_paths(["a.csv", " a.csv ", "", None]), ["a.csv"])

	def test_build_file_context_csv_preview_and_abs_path(self):
		csv_path = self.root / "sales.csv"
		csv_path.write_text("name,amount\nAlice,10\nBob,20\n", encoding="utf-8")
		ctx = build_file_context([str(csv_path)])
		self.assertIn("User has attached the following files:", ctx)
		self.assertIn("sales.csv", ctx)
		self.assertIn("CSV", ctx)
		self.assertIn(str(csv_path.resolve()), ctx)
		self.assertIn("Alice,10", ctx)
		self.assertIn("name,amount", ctx)

	def test_missing_file_noted(self):
		ctx = build_file_context([str(self.root / "missing.json")])
		self.assertIn("NOT FOUND", ctx)

	def test_json_preview(self):
		jp = self.root / "rows.json"
		jp.write_text(json.dumps([{"a": 1}, {"a": 2}, {"a": 3}]), encoding="utf-8")
		ctx = build_file_context([str(jp)])
		self.assertIn("JSON", ctx)
		self.assertIn("'a': 1", ctx)

	def test_inject_file_context(self):
		txt = self.root / "notes.txt"
		txt.write_text("line1\nline2\n", encoding="utf-8")
		out = inject_file_context("summarize this", [str(txt)])
		self.assertIn("Task: summarize this", out)
		self.assertIn("notes.txt", out)
		self.assertIn("line1", out)

	def test_never_mentions_secrets(self):
		ctx = build_file_context([])
		self.assertEqual(ctx, "")
		# Guard against accidental secret tokens in module-level strings.
		from libs.context import file_context as mod

		src = Path(mod.__file__).read_text(encoding="utf-8").lower()
		for bad in ("openai_api_key=", "sk-", "password="):
			self.assertNotIn(bad, src)


if __name__ == "__main__":
	unittest.main()
