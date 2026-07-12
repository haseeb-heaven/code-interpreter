# -*- coding: utf-8 -*-
"""Unit + opt-in live tests for user-scenario automation.

Policy cases always run (no keys). Full live CLI suite runs when
``LIVE_SCENARIOS=1`` (or via ``scripts/run_live_scenarios.py``).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.live.scenarios.cases import build_scenario_cases
from tests.live.scenarios.fixtures import ensure_scenario_fixtures, resolve_test_data_dir
from tests.live.scenarios.runner import run_case, run_suite


class TestScenarioFixtures(unittest.TestCase):
	def test_ensure_fixtures_under_temp_dir(self):
		with tempfile.TemporaryDirectory() as tmp:
			meta = ensure_scenario_fixtures(Path(tmp))
			self.assertTrue(Path(meta["paths"]["json"]).is_file())
			self.assertTrue(Path(meta["paths"]["png"]).is_file())
			self.assertIn("live_scenario_fixtures", meta["fixture_dir"])

	def test_resolve_uses_env(self):
		with tempfile.TemporaryDirectory() as tmp:
			with patch.dict(os.environ, {"INTERPRETER_TEST_DATA_DIR": tmp}, clear=False):
				path = resolve_test_data_dir(require=True)
				self.assertEqual(path, Path(tmp).resolve())


class TestPolicyScenariosAlways(unittest.TestCase):
	def test_policy_cases_pass(self):
		with tempfile.TemporaryDirectory() as tmp:
			os.environ["INTERPRETER_TEST_DATA_DIR"] = tmp
			fixtures = ensure_scenario_fixtures(Path(tmp))
			cases = [c for c in build_scenario_cases(fixtures) if c.kind == "policy"]
			self.assertGreaterEqual(len(cases), 4)
			for case in cases:
				row = run_case(case)
				self.assertEqual(row["status"], "PASS", f"{case.id}: {row}")


class TestLiveScenarioSuiteOptIn(unittest.TestCase):
	"""Full suite when LIVE_SCENARIOS=1; otherwise policy-only smoke via run_suite."""

	def test_run_suite_policy_only_fail_zero(self):
		with tempfile.TemporaryDirectory() as tmp:
			os.environ["INTERPRETER_TEST_DATA_DIR"] = tmp
			payload = run_suite(policy_only=True, report_dir=Path(tmp) / "reports")
			self.assertEqual(payload["summary"]["FAIL"], 0)
			self.assertGreater(payload["summary"]["PASS"], 0)
			self.assertTrue(Path(payload["report_json"]).is_file())

	@unittest.skipUnless(
		os.getenv("LIVE_SCENARIOS", "").strip() in ("1", "true", "yes"),
		"Set LIVE_SCENARIOS=1 to run full live CLI scenarios",
	)
	def test_full_live_suite_fail_zero(self):
		data = os.getenv("INTERPRETER_TEST_DATA_DIR") or os.getenv("TEST_DATA_DIR")
		if not data:
			self.skipTest("INTERPRETER_TEST_DATA_DIR required for full live suite")
		payload = run_suite(
			report_dir=Path("scratch") / "live_scenario_reports",
		)
		self.assertEqual(
			payload["summary"]["FAIL"],
			0,
			f"live FAIL>0: {[r for r in payload['rows'] if r['status']=='FAIL']}",
		)


if __name__ == "__main__":
	unittest.main()
