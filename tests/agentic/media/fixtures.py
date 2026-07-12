# -*- coding: utf-8 -*-
"""Resolve INTERPRETER_TEST_DATA_DIR and generate media fixtures."""

from __future__ import annotations

import json
import logging
import os
import struct
import wave
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TestDataDirError(RuntimeError):
	"""Raised when the test data directory env var is required but missing."""


def resolve_test_data_dir(*, require: bool = False) -> Path | None:
	"""Return INTERPRETER_TEST_DATA_DIR or alias TEST_DATA_DIR."""
	raw = (
		os.environ.get("INTERPRETER_TEST_DATA_DIR")
		or os.environ.get("TEST_DATA_DIR")
		or ""
	).strip()
	if not raw:
		if require:
			raise TestDataDirError(
				"Set INTERPRETER_TEST_DATA_DIR (or TEST_DATA_DIR) for media fixtures"
			)
		return None
	path = Path(raw).expanduser().resolve()
	path.mkdir(parents=True, exist_ok=True)
	return path


def _write_minimal_png(path: Path) -> None:
	"""Write a tiny valid 1x1 PNG without requiring Pillow."""
	# Precomputed 1x1 red PNG
	png = bytes.fromhex(
		"89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
		"de0000000c4944415408d763f8cfc000000003000101e2e27c0000000049454e"
		"44ae426082"
	)
	path.write_bytes(png)


def _write_minimal_pdf(path: Path) -> None:
	"""Write a minimal one-page PDF with printable text."""
	content = b"""BT /F1 12 Tf 72 720 Td (Agentic media fixture PDF) Tj ET"""
	objects = []
	objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
	objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
	objects.append(
		b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
		b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
	)
	stream = b"<< /Length %d >>stream\n" % len(content) + content + b"\nendstream\n"
	objects.append(b"4 0 obj" + stream + b"endobj\n")
	objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

	out = bytearray(b"%PDF-1.4\n")
	offsets = [0]
	for obj in objects:
		offsets.append(len(out))
		out.extend(obj)
	xref_pos = len(out)
	out.extend(b"xref\n0 %d\n" % (len(offsets)))
	out.extend(b"0000000000 65535 f \n")
	for off in offsets[1:]:
		out.extend(b"%010d 00000 n \n" % off)
	out.extend(
		b"trailer<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
		% (len(offsets), xref_pos)
	)
	path.write_bytes(bytes(out))


def _write_minimal_wav(path: Path, *, seconds: float = 0.25, rate: int = 8000) -> None:
	nframes = int(rate * seconds)
	with wave.open(str(path), "w") as wf:
		wf.setnchannels(1)
		wf.setsampwidth(2)
		wf.setframerate(rate)
		# short silence
		silence = struct.pack("<h", 0) * nframes
		wf.writeframes(silence)


def ensure_media_fixtures(root: Path | None = None) -> dict[str, Any]:
	"""Create json/png/pdf/wav (and optional mp4) under root fixtures dir."""
	base = root or resolve_test_data_dir(require=True)
	assert base is not None
	fixture_dir = base / "agentic_media_fixtures"
	fixture_dir.mkdir(parents=True, exist_ok=True)

	json_path = fixture_dir / "sample.json"
	png_path = fixture_dir / "sample.png"
	pdf_path = fixture_dir / "sample.pdf"
	wav_path = fixture_dir / "sample.wav"
	csv_out = fixture_dir / "out.csv"

	if not json_path.is_file():
		json_path.write_text(
			json.dumps({"rows": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]}, indent=2),
			encoding="utf-8",
		)
	if not png_path.is_file():
		try:
			from PIL import Image

			Image.new("RGB", (64, 64), color=(30, 144, 255)).save(png_path)
		except Exception:  # noqa: BLE001 — fall back to raw PNG
			logger.debug("Pillow unavailable; writing minimal PNG", exc_info=True)
			_write_minimal_png(png_path)
	if not pdf_path.is_file():
		try:
			from reportlab.pdfgen import canvas

			c = canvas.Canvas(str(pdf_path))
			c.drawString(72, 720, "Agentic media fixture PDF")
			c.save()
		except Exception:  # noqa: BLE001
			logger.debug("reportlab unavailable; writing minimal PDF", exc_info=True)
			_write_minimal_pdf(pdf_path)
	if not wav_path.is_file():
		_write_minimal_wav(wav_path)

	mp4_path = fixture_dir / "sample.mp4"
	# Optional: leave missing; video cases soft-skip
	paths = {
		"json": str(json_path.resolve()),
		"png": str(png_path.resolve()),
		"pdf": str(pdf_path.resolve()),
		"wav": str(wav_path.resolve()),
		"csv_out": str(csv_out.resolve()),
		"mp4": str(mp4_path.resolve()) if mp4_path.is_file() else "",
	}
	return {
		"fixture_dir": str(fixture_dir.resolve()),
		"root": str(base.resolve()),
		"paths": paths,
	}
