# -*- coding: utf-8 -*-
"""Smoke tests for the live-scenario fixture sync."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tests.live.scenarios.fixtures import ensure_scenario_fixtures


class TestScenarioFixturesNewFileTypes(unittest.TestCase):
	def test_new_dummy_media_fixtures_are_synced(self):
		with tempfile.TemporaryDirectory() as tmp:
			result = ensure_scenario_fixtures(root=Path(tmp))
			paths = result["paths"]
			for key in (
				"archive_zip", "audio_mp3", "java_src", "app_sqlite",
				"docx_doc", "svg_logo", "video_webm",
			):
				self.assertTrue(os.path.isfile(paths[key]), f"{key} -> {paths[key]}")
				self.assertGreater(os.path.getsize(paths[key]), 0)


if __name__ == "__main__":
	unittest.main()
