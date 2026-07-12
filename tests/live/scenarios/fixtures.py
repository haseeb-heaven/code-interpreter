# -*- coding: utf-8 -*-
"""Live user-scenario fixtures under INTERPRETER_TEST_DATA_DIR (never hardcoded)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TestDataDirError(RuntimeError):
	"""Raised when INTERPRETER_TEST_DATA_DIR is required but missing."""


def resolve_test_data_dir(*, require: bool = False) -> Optional[Path]:
	"""Return INTERPRETER_TEST_DATA_DIR or alias TEST_DATA_DIR."""
	raw = (
		os.environ.get("INTERPRETER_TEST_DATA_DIR")
		or os.environ.get("TEST_DATA_DIR")
		or ""
	).strip()
	if not raw:
		if require:
			raise TestDataDirError(
				"Set INTERPRETER_TEST_DATA_DIR (or TEST_DATA_DIR) for live scenario fixtures"
			)
		return None
	path = Path(raw).expanduser().resolve()
	path.mkdir(parents=True, exist_ok=True)
	return path


def _write_minimal_png(path: Path) -> None:
	png = bytes.fromhex(
		"89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
		"de0000000c4944415408d763f8cfc000000003000101e2e27c0000000049454e"
		"44ae426082"
	)
	path.write_bytes(png)


def ensure_scenario_fixtures(root: Optional[Path] = None) -> dict[str, Any]:
	"""Create JSON/PNG/CSV/text fixtures under ``<data>/live_scenario_fixtures``."""
	base = root or resolve_test_data_dir(require=True)
	assert base is not None
	fixture_dir = base / "live_scenario_fixtures"
	fixture_dir.mkdir(parents=True, exist_ok=True)
	out_dir = fixture_dir / "output"
	out_dir.mkdir(parents=True, exist_ok=True)
	apps_dir = fixture_dir / "apps"
	apps_dir.mkdir(parents=True, exist_ok=True)

	json_path = fixture_dir / "sales.json"
	if not json_path.is_file():
		payload = [
			{"month": "Jan", "revenue": 10, "cost": 4},
			{"month": "Feb", "revenue": 15, "cost": 6},
			{"month": "Mar", "revenue": 12, "cost": 5},
			{"month": "Apr", "revenue": 18, "cost": 7},
		]
		json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

	png_path = fixture_dir / "sample.png"
	if not png_path.is_file():
		_write_minimal_png(png_path)

	csv_path = fixture_dir / "sales.csv"
	if not csv_path.is_file():
		csv_path.write_text(
			"month,revenue,cost\nJan,10,4\nFeb,15,6\nMar,12,5\nApr,18,7\n",
			encoding="utf-8",
		)

	edit_csv = fixture_dir / "editable.csv"
	# Always reset editable so edit scenarios are deterministic
	edit_csv.write_text("name,score\nAlice,1\nBob,2\n", encoding="utf-8")

	notes_path = fixture_dir / "notes.txt"
	if not notes_path.is_file():
		notes_path.write_text(
			"Open Code Interpreter live scenario notes.\n"
			"This document discusses JSON conversion, charts, and sandbox safety.\n"
			"Key themes: automation, artifacts, and soft-skip for quota.\n",
			encoding="utf-8",
		)

	md_path = fixture_dir / "brief.md"
	if not md_path.is_file():
		md_path.write_text(
			"# Briefing\n\nSummarize this markdown for the live suite.\n\n"
			"- Point A: convert data\n- Point B: plot charts\n",
			encoding="utf-8",
		)

	paths = {
		"json": str(json_path.resolve()),
		"png": str(png_path.resolve()),
		"csv": str(csv_path.resolve()),
		"edit_csv": str(edit_csv.resolve()),
		"notes": str(notes_path.resolve()),
		"md": str(md_path.resolve()),
		"abs_write": str((out_dir / "user_intent_out.txt").resolve()),
		"chart_png": str((out_dir / "chart_mpl.png").resolve()),
		"chart_plotly": str((out_dir / "chart_plotly.html").resolve()),
		"jpg_out": str((out_dir / "converted.jpg").resolve()),
		"crop_out": str((out_dir / "cropped.jpg").resolve()),
		"csv_from_json": str((out_dir / "sales_from_json.csv").resolve()),
		"report_txt": str((out_dir / "report.txt").resolve()),
		"summary_txt": str((out_dir / "summary.txt").resolve()),
		"analysis_txt": str((out_dir / "analysis.txt").resolve()),
		"app_script": str((apps_dir / "hello_app.py").resolve()),
		"app_out": str((apps_dir / "hello_out.txt").resolve()),
		"search_report": str((out_dir / "search_report.txt").resolve()),
		"fixture_dir": str(fixture_dir.resolve()),
		"out_dir": str(out_dir.resolve()),
		"apps_dir": str(apps_dir.resolve()),
	}
	logger.info("Live scenario fixtures ready under %s", fixture_dir)
	return {"base": str(base), "fixture_dir": str(fixture_dir), "paths": paths}
