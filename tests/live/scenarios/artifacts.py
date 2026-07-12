# -*- coding: utf-8 -*-
"""Artifact expectations and verification for live scenarios."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class ArtifactExpect:
	"""Declare an output file the scenario must produce."""

	path: str
	min_bytes: int = 1
	kind: str = "any"  # any|png|jpg|csv|json|html|txt|md
	contains: Optional[str] = None
	optional: bool = False  # if True, missing → SKIP not FAIL


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def _sniff_ok(path: Path, kind: str) -> tuple[bool, str]:
	data = path.read_bytes()[:64]
	if kind == "png":
		if data.startswith(_PNG_MAGIC):
			return True, "png magic"
		return False, "not a PNG"
	if kind == "jpg":
		if data.startswith(_JPEG_MAGIC):
			return True, "jpeg magic"
		return False, "not a JPEG"
	if kind == "html":
		text = path.read_text(encoding="utf-8", errors="replace")[:500].lower()
		if "<html" in text or "<div" in text or "plotly" in text:
			return True, "html-ish"
		return False, "not html-like"
	if kind == "csv":
		try:
			with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
				row = next(csv.reader(fh), None)
			if row and len(row) >= 1:
				return True, f"csv header cols={len(row)}"
			return False, "empty csv"
		except Exception as exc:  # noqa: BLE001
			return False, f"csv read error: {exc}"
	if kind == "json":
		try:
			json.loads(path.read_text(encoding="utf-8"))
			return True, "json ok"
		except Exception as exc:  # noqa: BLE001
			return False, f"json error: {exc}"
	if kind in ("txt", "md", "any"):
		return True, "bytes present"
	return True, "ok"


def verify_artifacts(expects: list[ArtifactExpect]) -> dict[str, Any]:
	"""Return ``{status, detail, checked: [{path, ok, bytes, note}]}``."""
	checked: list[dict[str, Any]] = []
	failures: list[str] = []
	skips: list[str] = []

	for exp in expects or []:
		path = Path(exp.path)
		entry: dict[str, Any] = {
			"path": str(path),
			"ok": False,
			"bytes": 0,
			"note": "",
			"kind": exp.kind,
		}
		if not path.is_file():
			entry["note"] = "missing"
			checked.append(entry)
			if exp.optional:
				skips.append(f"optional missing: {path.name}")
			else:
				failures.append(f"missing: {path}")
			continue

		size = path.stat().st_size
		entry["bytes"] = size
		if size < int(exp.min_bytes):
			entry["note"] = f"too small ({size}<{exp.min_bytes})"
			checked.append(entry)
			failures.append(entry["note"] + f" @ {path.name}")
			continue

		ok, note = _sniff_ok(path, exp.kind)
		entry["note"] = note
		if not ok:
			checked.append(entry)
			failures.append(f"{path.name}: {note}")
			continue

		if exp.contains:
			text = path.read_text(encoding="utf-8", errors="replace")
			if exp.contains not in text:
				entry["note"] = f"missing content {exp.contains!r}"
				entry["ok"] = False
				checked.append(entry)
				failures.append(entry["note"] + f" @ {path.name}")
				continue

		entry["ok"] = True
		checked.append(entry)

	if failures:
		return {
			"status": "FAIL",
			"detail": "; ".join(failures),
			"checked": checked,
		}
	if skips and not any(c["ok"] for c in checked):
		return {
			"status": "SKIP",
			"detail": "; ".join(skips),
			"checked": checked,
		}
	detail_bits = [
		f"{Path(c['path']).name}:{c['bytes']}b" for c in checked if c.get("ok")
	]
	return {
		"status": "PASS",
		"detail": "artifacts ok (" + ", ".join(detail_bits) + ")",
		"checked": checked,
	}
