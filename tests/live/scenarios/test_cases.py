# -*- coding: utf-8 -*-
"""Structural checks for the dummy_media ScenarioCase additions."""

from __future__ import annotations

import unittest

from tests.live.scenarios.cases import build_scenario_cases

_EXPECTED_DUMMY_IDS = {
	"dummy_zip_list", "dummy_zip_extract", "dummy_zip_create",
	"dummy_java_summarize", "dummy_sqlite_report", "dummy_sqlite_edit",
	"dummy_docx_extract_text", "dummy_svg_analyze", "dummy_webm_probe",
	"dummy_mp3_probe",
}


class TestDummyMediaScenarioCases(unittest.TestCase):
	def test_all_dummy_media_cases_present(self):
		cases = build_scenario_cases()
		ids = {c.id for c in cases}
		missing = _EXPECTED_DUMMY_IDS - ids
		self.assertFalse(missing, f"missing scenario ids: {missing}")

	def test_all_dummy_media_cases_cover_create_analyze_summarize_convert_edit(self):
		cases = {c.id: c for c in build_scenario_cases() if c.id in _EXPECTED_DUMMY_IDS}
		categories = {c.category for c in cases.values()}
		self.assertTrue({"create", "analyze", "summarize", "convert", "edit"} <= categories)


if __name__ == "__main__":
	unittest.main()
