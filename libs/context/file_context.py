# -*- coding: utf-8 -*-
"""Local file attachment context for LLM prompts (Issue #221).

Builds a prompt preface listing attached files with absolute paths and
small previews for CSV/JSON/TXT so the model can generate correct code.
Never logs secrets or .env contents.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

SUPPORTED_PREVIEW_TYPES = {".csv", ".json", ".txt", ".tsv", ".log"}
MAX_PREVIEW_ROWS = 5


def _format_size(num_bytes: int) -> str:
	"""Human-readable file size."""
	try:
		kb = num_bytes / 1024.0
		if kb < 1024:
			return f"{kb:.1f} KB"
		return f"{kb / 1024.0:.1f} MB"
	except Exception:
		return "unknown size"


def _get_preview(path: Path, ext: str) -> str:
	"""Return an indented preview of the first rows / keys of a text-like file."""
	try:
		if ext in (".csv", ".tsv"):
			delim = "\t" if ext == ".tsv" else ","
			with open(path, newline="", encoding="utf-8", errors="ignore") as handle:
				reader = csv.reader(handle, delimiter=delim)
				rows: List[List[str]] = []
				for idx, row in enumerate(reader):
					if idx > MAX_PREVIEW_ROWS:
						break
					rows.append(row)
			if not rows:
				return ""
			return "\n".join("    " + ",".join(r) for r in rows)

		if ext == ".json":
			with open(path, encoding="utf-8", errors="ignore") as handle:
				data = json.load(handle)
			if isinstance(data, list):
				return "    " + str(data[:MAX_PREVIEW_ROWS])
			return "    " + str(data)[:300]

		if ext in (".txt", ".log"):
			with open(path, encoding="utf-8", errors="ignore") as handle:
				lines = []
				for _ in range(MAX_PREVIEW_ROWS):
					line = handle.readline()
					if not line:
						break
					lines.append("    " + line.rstrip())
			return "\n".join(lines)
	except Exception as exc:
		logger.warning("Preview failed for %s: %s", path, exc)
		return ""
	return ""


def normalize_paths(paths: Optional[Sequence[str]]) -> List[str]:
	"""Deduplicate and strip path strings; drop empties."""
	if not paths:
		return []
	seen = set()
	out: List[str] = []
	for raw in paths:
		if raw is None:
			continue
		text = str(raw).strip().strip('"').strip("'")
		if not text or text in seen:
			continue
		seen.add(text)
		out.append(text)
	return out


def build_file_context(paths: Iterable[str]) -> str:
	"""Build a context string describing attached files for the LLM prompt."""
	path_list = normalize_paths(list(paths))
	if not path_list:
		return ""

	lines = ["User has attached the following files:"]
	for path_str in path_list:
		try:
			path = Path(path_str).expanduser().resolve()
		except Exception as exc:
			logger.warning("Could not resolve path %r: %s", path_str, exc)
			lines.append(f"  - {path_str} (INVALID PATH — skip this file)")
			continue

		if not path.exists():
			lines.append(f"  - {path_str} (NOT FOUND — skip this file)")
			continue

		try:
			size_str = _format_size(path.stat().st_size)
			ext = path.suffix.lower() or ".bin"
			kind = ext[1:].upper() if ext.startswith(".") else ext.upper()
			lines.append(
				f"  - {path.name} ({kind}, {size_str}, absolute path: {path})"
			)
			if ext in SUPPORTED_PREVIEW_TYPES:
				preview = _get_preview(path, ext)
				if preview:
					lines.append(f"    Preview (first {MAX_PREVIEW_ROWS} rows):")
					lines.append(preview)
		except OSError as exc:
			logger.warning("Stat failed for %s: %s", path, exc)
			lines.append(f"  - {path_str} (UNREADABLE — skip this file)")

	return "\n".join(lines)


def inject_file_context(task: str, paths: Optional[Sequence[str]]) -> str:
	"""Prepend file context to a user task when attachments exist."""
	context = build_file_context(paths or [])
	task_text = (task or "").strip()
	if not context:
		return task_text
	if not task_text:
		return context
	return f"{context}\n\nTask: {task_text}"
