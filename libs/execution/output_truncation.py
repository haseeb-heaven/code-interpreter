# -*- coding: utf-8 -*-
"""Truncate long execution output for readable terminals (Issue #223)."""

from __future__ import annotations

MAX_OUTPUT_LINES = 50
MAX_OUTPUT_CHARS = 5000


def format_output(
	raw_output: str,
	*,
	max_lines: int = MAX_OUTPUT_LINES,
	max_chars: int = MAX_OUTPUT_CHARS,
) -> str:
	"""Truncate long stdout while keeping head + tail context."""
	if raw_output is None:
		return ""
	text = str(raw_output)
	lines = text.splitlines()
	if len(lines) > max_lines:
		kept = (
			lines[:20]
			+ [f"... [{len(lines) - 40} lines truncated] ..."]
			+ lines[-20:]
		)
		text = "\n".join(kept)
	if len(text) > max_chars:
		return text[:max_chars] + f"\n... [truncated, {len(raw_output)} total chars]"
	return text
