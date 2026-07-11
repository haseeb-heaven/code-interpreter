"""Built-in tool for glob file search."""

from __future__ import annotations

import glob
import logging
from pathlib import Path

from libs.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class GlobSearchTool(BaseTool):
	"""Search for files matching a glob pattern."""

	name = "glob_search"
	description = "Search for files matching a glob pattern."
	input_schema = {
		"type": "object",
		"properties": {
			"pattern": {
				"type": "string",
				"description": "Glob pattern, e.g. '**/*.py'",
			},
		},
		"required": ["pattern"],
	}

	def __init__(self, cwd=None):
		self.cwd = Path(cwd or Path.cwd()).resolve()

	def run(self, input_data):
		pattern = (input_data or {}).get("pattern")
		if not pattern or not str(pattern).strip():
			return ToolResult(success=False, error="pattern is required")

		try:
			# Resolve relative patterns against cwd for predictable results.
			raw = str(pattern)
			search_root = self.cwd
			if Path(raw).is_absolute():
				matches = sorted(glob.glob(raw, recursive=True))
			else:
				matches = sorted(
					glob.glob(str(search_root / raw), recursive=True)
				)
				# Prefer paths relative to cwd when possible.
				rel = []
				for match in matches:
					try:
						rel.append(str(Path(match).resolve().relative_to(search_root)))
					except ValueError:
						rel.append(match)
				matches = rel

			output = "\n".join(matches) if matches else f"No matches for: {pattern}"
			logger.info("[glob_search] pattern=%r -> %d matches", pattern, len(matches))
			return ToolResult(
				success=True,
				output=output,
				metadata={"pattern": str(pattern), "count": len(matches)},
			)
		except Exception as exc:
			logger.exception("[glob_search] Failed")
			return ToolResult(success=False, error=str(exc))
