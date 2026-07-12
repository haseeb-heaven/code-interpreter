# -*- coding: utf-8 -*-
"""Case definitions for agentic media live suite (easy → medium → complex)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from tests.agentic.media.fixtures import ensure_media_fixtures

logger = logging.getLogger(__name__)


@dataclass
class SuiteCase:
	id: str
	tier: str  # easy | medium | complex
	category: str  # media | agentic (never provider)
	prompt: str
	agentic: bool = False
	extra_args: list[str] = field(default_factory=list)
	model: str | None = None
	expect_marker: str | None = None
	language: str = "python"


def build_cases(fixtures: dict[str, Any] | None = None) -> list[SuiteCase]:
	"""Build media/agentic cases using paths from fixtures (no provider matrix)."""
	meta = fixtures or ensure_media_fixtures()
	p = meta["paths"]
	fixture_dir = meta["fixture_dir"]
	json_p = p["json"]
	png_p = p["png"]
	pdf_p = p["pdf"]
	wav_p = p["wav"]
	csv_out = p["csv_out"]
	mp4_p = p.get("mp4") or ""

	cases: list[SuiteCase] = [
		# --- easy ---
		SuiteCase(
			id="easy_json_to_csv",
			tier="easy",
			category="media",
			prompt=(
				f"Read the JSON file at {json_p} and write a CSV to {csv_out} "
				f"with columns a,b. Print exactly DONE_CSV when finished."
			),
			extra_args=["--no-sandbox"],
			expect_marker="DONE_CSV",
		),
		SuiteCase(
			id="easy_classic_print",
			tier="easy",
			category="media",
			prompt="Write Python that prints exactly MEDIA_EASY_OK.",
			expect_marker="MEDIA_EASY_OK",
		),
		SuiteCase(
			id="easy_agentic_hello",
			tier="easy",
			category="agentic",
			prompt="Print exactly AGENTIC_HELLO using a short Python program.",
			agentic=True,
			expect_marker="AGENTIC_HELLO",
		),
		# --- medium ---
		SuiteCase(
			id="medium_matplotlib_chart",
			tier="medium",
			category="media",
			prompt=(
				f"Load JSON from {json_p}. Plot a,b as a simple 2D line chart with matplotlib. "
				f"Save PNG to {fixture_dir}/chart2d.png and print CHART2D_OK."
			),
			extra_args=["--no-sandbox"],
			expect_marker="CHART2D_OK",
		),
		SuiteCase(
			id="medium_png_crop",
			tier="medium",
			category="media",
			prompt=(
				f"Open PNG {png_p}, center-crop to about 32x32 (or as close as possible), "
				f"save JPG to {fixture_dir}/cropped.jpg, print PNG_CROP_OK."
			),
			extra_args=["--no-sandbox"],
			expect_marker="PNG_CROP_OK",
		),
		SuiteCase(
			id="medium_pdf_summarize",
			tier="medium",
			category="media",
			prompt=(
				f"Open PDF {pdf_p} if possible (pypdf/pdfplumber/PyPDF2) and print a one-line "
				f"summary that includes PDF_OK. If libraries missing, print PDF_OK anyway "
				f"with note 'deps missing'."
			),
			extra_args=["--no-sandbox"],
			expect_marker="PDF_OK",
		),
		SuiteCase(
			id="medium_wav_crop",
			tier="medium",
			category="media",
			prompt=(
				f"Using stdlib wave, open {wav_p}, write a shorter WAV to "
				f"{fixture_dir}/cropped.wav (first half of frames), print WAV_OK."
			),
			extra_args=["--no-sandbox"],
			expect_marker="WAV_OK",
		),
		# --- complex ---
		SuiteCase(
			id="complex_3d_chart",
			tier="complex",
			category="media",
			prompt=(
				f"Create a simple 3D scatter with mpl_toolkits.mplot3d using a few points, "
				f"save to {fixture_dir}/chart3d.png, print CHART3D_OK."
			),
			extra_args=["--no-sandbox"],
			expect_marker="CHART3D_OK",
		),
		SuiteCase(
			id="complex_agentic_pipeline",
			tier="complex",
			category="agentic",
			prompt=(
				f"Multi-step: (1) convert {json_p} to CSV at {fixture_dir}/pipe.csv "
				f"(2) make a tiny matplotlib bar chart saved to {fixture_dir}/pipe.png "
				f"(3) print PIPELINE_DONE. Use --agentic style reasoning if helpful."
			),
			agentic=True,
			extra_args=["--no-sandbox"],
			expect_marker="PIPELINE_DONE",
		),
		SuiteCase(
			id="complex_video_frame",
			tier="complex",
			category="media",
			prompt=(
				f"If ffmpeg and mp4 at '{mp4_p}' exist, extract one frame to "
				f"{fixture_dir}/frame.png and print VIDEO_OK. "
				f"If missing, print VIDEO_SKIP_DEPS."
			),
			extra_args=["--no-sandbox"],
			expect_marker="VIDEO_",
		),
	]
	logger.info("Built %d media suite cases under %s", len(cases), fixture_dir)
	return cases
