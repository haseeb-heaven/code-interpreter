# -*- coding: utf-8 -*-
"""Unit + opt-in live tests for user-scenario automation (EASY tier focus)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.live.scenarios.cases import build_scenario_cases
from tests.live.scenarios.fixtures import (
	REPO_INPUT,
	ensure_scenario_fixtures,
	resolve_test_data_dir,
)
from tests.live.scenarios.runner import run_case, run_suite


class TestCommittedFixtures(unittest.TestCase):
	def test_repo_input_fixtures_exist(self):
		self.assertTrue(REPO_INPUT.is_dir(), REPO_INPUT)
		for name in (
			"sales.json",
			"sales.csv",
			"editable.csv",
			"notes.txt",
			"brief.md",
			"sample.png",
			"sample.pdf",
		):
			path = REPO_INPUT / name
			self.assertTrue(path.is_file(), path)
			self.assertGreater(path.stat().st_size, 0, name)

	def test_sync_into_workdir(self):
		with tempfile.TemporaryDirectory() as tmp:
			meta = ensure_scenario_fixtures(Path(tmp))
			self.assertTrue(Path(meta["paths"]["json"]).is_file())
			self.assertTrue(Path(meta["paths"]["png"]).is_file())
			self.assertIn("tests", meta["repo_fixtures"].replace("\\", "/"))
			self.assertIn("live_scenario_fixtures", meta["fixture_dir"])

	def test_resolve_uses_env(self):
		with tempfile.TemporaryDirectory() as tmp:
			with patch.dict(os.environ, {"INTERPRETER_TEST_DATA_DIR": tmp}, clear=False):
				path = resolve_test_data_dir(require=True)
				self.assertEqual(path, Path(tmp).resolve())


class TestEasyCaseCoverage(unittest.TestCase):
	"""TDD: required EASY user scenarios must be present."""

	REQUIRED_EASY_IDS = {
		"offline_convert_json_csv",
		"offline_chart_matplotlib",
		"offline_summarize_notes",
		"offline_edit_text_append",
		"slash_help_free_smoke",
	}

	def test_easy_required_cases_exist(self):
		with tempfile.TemporaryDirectory() as tmp:
			meta = ensure_scenario_fixtures(Path(tmp))
			cases = build_scenario_cases(meta)
			easy = {c.id: c for c in cases if c.tier == "easy"}
			for cid in self.REQUIRED_EASY_IDS:
				self.assertIn(cid, easy, f"missing easy case {cid}")
			self.assertEqual(easy["offline_chart_matplotlib"].tier, "easy")
			self.assertTrue(easy["offline_convert_json_csv"].expect_artifacts)
			self.assertTrue(easy["offline_chart_matplotlib"].expect_artifacts)
			self.assertTrue(easy["offline_summarize_notes"].expect_artifacts)
			self.assertTrue(easy["offline_edit_text_append"].expect_artifacts)


class TestSlashSmokeMocked(unittest.TestCase):
	"""Slash /help /free must not crash (mocked — no live REPL hang)."""

	def test_help_and_free_catalog_smoke(self):
		import inspect

		from libs.free_llms import FreeLLMCatalog
		from libs.utility_manager import UtilityManager

		cat = FreeLLMCatalog.load()
		table = cat.format_table()
		self.assertTrue(isinstance(table, str) and len(table) > 10)
		self.assertNotIn("Traceback", table)
		self.assertTrue(cat.list_ids())

		src = inspect.getsource(UtilityManager.display_help)
		self.assertIn("/help", src)
		self.assertIn("/free", src)


class TestEasyOfflineSuite(unittest.TestCase):
	def test_easy_offline_fail_zero(self):
		with tempfile.TemporaryDirectory() as tmp:
			os.environ["INTERPRETER_TEST_DATA_DIR"] = tmp
			payload = run_suite(
				offline_only=True,
				tiers={"easy"},
				report_dir=Path(tmp) / "scratch",
			)
			# Slash may SKIP when local endpoint is down — not a failure.
			fails = [r for r in payload["rows"] if r["status"] == "FAIL"]
			self.assertEqual(fails, [], fails)
			self.assertGreater(payload["summary"]["PASS"], 0)
			self.assertTrue(Path(payload["report_md"]).is_file())
			self.assertTrue(Path(payload["report_html"]).is_file())

			by_id = {r["id"]: r for r in payload["rows"]}
			for cid in (
				"offline_convert_json_csv",
				"offline_summarize_notes",
				"offline_edit_text_append",
			):
				self.assertEqual(by_id[cid]["status"], "PASS", by_id[cid])
			chart = by_id["offline_chart_matplotlib"]
			self.assertIn(chart["status"], ("PASS", "SKIP"), chart)
			slash = by_id["slash_help_free_smoke"]
			self.assertIn(slash["status"], ("PASS", "SKIP"), slash)


class TestLiveScenarioSuiteOptIn(unittest.TestCase):
	@unittest.skipUnless(
		os.getenv("LIVE_SCENARIOS", "").strip() in ("1", "true", "yes"),
		"Set LIVE_SCENARIOS=1 for full live CLI scenarios",
	)
	def test_full_live_suite_fail_zero(self):
		data = os.getenv("INTERPRETER_TEST_DATA_DIR") or os.getenv("TEST_DATA_DIR")
		if not data:
			self.skipTest("INTERPRETER_TEST_DATA_DIR required")
		payload = run_suite(tiers={"easy"}, report_dir=Path("scratch") / "easy_live")
		self.assertEqual(payload["summary"]["FAIL"], 0)


if __name__ == "__main__":
	unittest.main()
