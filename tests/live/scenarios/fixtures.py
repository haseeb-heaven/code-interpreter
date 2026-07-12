# -*- coding: utf-8 -*-
"""Copy committed ``tests/fixtures`` into INTERPRETER_TEST_DATA_DIR workdir."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Repo fixtures are the source of truth (committed).
REPO_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
REPO_INPUT = REPO_FIXTURES / "input"
REPO_EXPECTED = REPO_FIXTURES / "expected"


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
				"Set INTERPRETER_TEST_DATA_DIR (or TEST_DATA_DIR) for live scenario workdir"
			)
		return None
	path = Path(raw).expanduser().resolve()
	path.mkdir(parents=True, exist_ok=True)
	return path


def ensure_scenario_fixtures(root: Optional[Path] = None) -> dict[str, Any]:
	"""Sync committed fixtures into a writable workdir and return absolute paths.

	Source of truth: ``tests/fixtures/input`` (and ``expected/``).
	Workdir: ``<INTERPRETER_TEST_DATA_DIR>/live_scenario_fixtures/``.
	"""
	base = root or resolve_test_data_dir(require=True)
	assert base is not None

	if not REPO_INPUT.is_dir():
		raise FileNotFoundError(f"Committed fixtures missing: {REPO_INPUT}")

	fixture_dir = base / "live_scenario_fixtures"
	input_dir = fixture_dir / "input"
	expected_dir = fixture_dir / "expected"
	out_dir = fixture_dir / "output"
	apps_dir = fixture_dir / "apps"
	for d in (input_dir, expected_dir, out_dir, apps_dir):
		d.mkdir(parents=True, exist_ok=True)

	# Copy inputs (overwrite editable so edit scenarios stay deterministic)
	for src in REPO_INPUT.iterdir():
		if src.is_file():
			shutil.copy2(src, input_dir / src.name)
	if REPO_EXPECTED.is_dir():
		for src in REPO_EXPECTED.iterdir():
			if src.is_file():
				shutil.copy2(src, expected_dir / src.name)

	# Always reset editable sources from committed copies
	for name in ("editable.csv", "notes.txt"):
		src = REPO_INPUT / name
		if src.is_file():
			shutil.copy2(src, input_dir / name)

	def _p(*parts: str) -> str:
		return str(Path(fixture_dir, *parts).resolve())

	paths = {
		"json": _p("input", "sales.json"),
		"png": _p("input", "sample.png"),
		"pdf": _p("input", "sample.pdf"),
		"csv": _p("input", "sales.csv"),
		"edit_csv": _p("input", "editable.csv"),
		"notes": _p("input", "notes.txt"),
		"md": _p("input", "brief.md"),
		"expected_csv": _p("expected", "sales_from_json.csv"),
		"expected_summary": _p("expected", "summary_example.txt"),
		"expected_report": _p("expected", "report_example.txt"),
		"abs_write": _p("output", "user_intent_out.txt"),
		"chart_png": _p("output", "chart_mpl.png"),
		"chart_plotly": _p("output", "chart_plotly.html"),
		"jpg_out": _p("output", "converted.jpg"),
		"crop_out": _p("output", "cropped.jpg"),
		"csv_from_json": _p("output", "sales_from_json.csv"),
		"report_txt": _p("output", "report.txt"),
		"summary_txt": _p("output", "summary.txt"),
		"analysis_txt": _p("output", "analysis.txt"),
		"app_script": _p("apps", "hello_app.py"),
		"app_out": _p("apps", "hello_out.txt"),
		"search_report": _p("output", "search_report.txt"),
		"fixture_dir": str(fixture_dir.resolve()),
		"repo_fixtures": str(REPO_FIXTURES.resolve()),
		"out_dir": str(out_dir.resolve()),
		"apps_dir": str(apps_dir.resolve()),
	}
	logger.info("Synced fixtures %s -> %s", REPO_FIXTURES, fixture_dir)
	return {
		"base": str(base),
		"fixture_dir": str(fixture_dir),
		"repo_fixtures": str(REPO_FIXTURES.resolve()),
		"paths": paths,
	}
