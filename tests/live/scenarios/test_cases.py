# -*- coding: utf-8 -*-
"""Structural checks for the dummy_media ScenarioCase additions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.live.scenarios.cases import build_scenario_cases
from tests.live.scenarios.fixtures import ensure_scenario_fixtures

_EXPECTED_DUMMY_IDS = {
	"dummy_zip_list", "dummy_zip_extract", "dummy_zip_create",
	"dummy_java_summarize", "dummy_sqlite_report", "dummy_sqlite_edit",
	"dummy_docx_extract_text", "dummy_svg_analyze", "dummy_webm_probe",
	"dummy_mp3_probe",
}


class TestDummyMediaScenarioCases(unittest.TestCase):
	"""Offline structural checks — no live LLM calls, but ``build_scenario_cases``
	needs a fixtures workdir. Use an explicit tempdir (like
	``TestEasyCaseCoverage`` in ``test_live_scenarios.py``) instead of relying
	on ``INTERPRETER_TEST_DATA_DIR`` being set in the environment, since CI
	does not set it for the plain unit-test step.
	"""

	def _build_cases(self):
		with tempfile.TemporaryDirectory() as tmp:
			meta = ensure_scenario_fixtures(Path(tmp))
			return build_scenario_cases(meta)

	def test_all_dummy_media_cases_present(self):
		cases = self._build_cases()
		ids = {c.id for c in cases}
		missing = _EXPECTED_DUMMY_IDS - ids
		self.assertFalse(missing, f"missing scenario ids: {missing}")

	def test_all_dummy_media_cases_cover_create_analyze_summarize_convert_edit(self):
		cases = {c.id: c for c in self._build_cases() if c.id in _EXPECTED_DUMMY_IDS}
		categories = {c.category for c in cases.values()}
		self.assertTrue({"create", "analyze", "summarize", "convert", "edit"} <= categories)


if __name__ == "__main__":
	unittest.main()
