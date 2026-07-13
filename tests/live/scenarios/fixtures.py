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

	# Absolute-path read target (must live under INTERPRETER_TEST_DATA_DIR workdir)
	abs_read = fixture_dir / "abs_readable.txt"
	abs_read.write_text(
		"ABS_READ_PAYLOAD=hello_from_test_data_dir\n",
		encoding="utf-8",
	)

	def _p(*parts: str) -> str:
		return str(Path(fixture_dir, *parts).resolve())

	paths = {
		"json": _p("input", "sales.json"),
		"png": _p("input", "sample.png"),
		"pdf": _p("input", "sample.pdf"),
		"csv": _p("input", "sales.csv"),
		"edit_csv": _p("input", "editable.csv"),
		"notes": _p("input", "notes.txt"),
		"archive_zip": _p("input", "archive.zip"),
		"audio_mp3": _p("input", "audio.mp3"),
		"java_src": _p("input", "Hello.java"),
		"app_sqlite": _p("input", "app.sqlite"),
		"docx_doc": _p("input", "document.docx"),
		"svg_logo": _p("input", "logo.svg"),
		"video_webm": _p("input", "clip.webm"),
		"md": _p("input", "brief.md"),
		"expected_csv": _p("expected", "sales_from_json.csv"),
		"expected_summary": _p("expected", "summary_example.txt"),
		"expected_report": _p("expected", "report_example.txt"),
		"abs_read": str(abs_read.resolve()),
		"abs_write": _p("output", "user_intent_out.txt"),
		"chart_png": _p("output", "chart_mpl.png"),
		"pipe_csv": _p("output", "pipeline_sales.csv"),
		"pipe_chart": _p("output", "pipeline_chart.png"),
		"stats_report": _p("output", "csv_stats_report.txt"),
		"chart_plotly": _p("output", "chart_plotly.html"),
		"jpg_out": _p("output", "converted.jpg"),
		"crop_out": _p("output", "cropped.jpg"),
		"crop_png_out": _p("output", "cropped.png"),
		"csv_from_json": _p("output", "sales_from_json.csv"),
		"report_txt": _p("output", "report.txt"),
		"summary_txt": _p("output", "summary.txt"),
		"agentic_summary": _p("output", "agentic_summary_report.txt"),
		"analysis_txt": _p("output", "analysis.txt"),
		"zip_list_txt": _p("output", "zip_list.txt"),
		"zip_extract_dir": _p("output", "zip_extract"),
		"zip_extract_manifest": _p("output", "zip_extract_manifest.txt"),
		"zip_created": _p("output", "created_archive.zip"),
		"java_summary_txt": _p("output", "java_summary.txt"),
		"sqlite_report_txt": _p("output", "sqlite_report.txt"),
		"sqlite_edit_copy": _p("output", "app_edited.sqlite"),
		"docx_text_txt": _p("output", "docx_text.txt"),
		"svg_analysis_txt": _p("output", "svg_analysis.txt"),
		"webm_probe_txt": _p("output", "webm_probe.txt"),
		"mp3_probe_txt": _p("output", "mp3_probe.txt"),
		"app_script": _p("apps", "hello_app.py"),
		"app_out": _p("apps", "hello_out.txt"),
		"complex_app": _p("apps", "complex_mini_app.py"),
		"complex_app_out": _p("apps", "complex_mini_out.txt"),
		"search_report": _p("output", "search_report.txt"),
		"free_fallback_marker": _p("output", "free_fallback_ok.txt"),
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
