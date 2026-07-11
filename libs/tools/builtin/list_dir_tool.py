"""Built-in tool for listing directory contents."""

from __future__ import annotations

import logging
from pathlib import Path

from libs.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ListDirTool(BaseTool):
	"""List files and directories at a path."""

	name = "list_dir"
	description = "List the contents of a directory."
	input_schema = {
		"type": "object",
		"properties": {
			"path": {
				"type": "string",
				"description": "Directory path. Defaults to '.' if not provided.",
			},
		},
		"required": [],
	}

	def __init__(self, cwd=None, restrict_to_cwd: bool = False):
		self.cwd = Path(cwd or Path.cwd()).resolve()
		self.restrict_to_cwd = restrict_to_cwd

	def run(self, input_data):
		raw_path = (input_data or {}).get("path") or "."
		path = Path(str(raw_path))
		resolved = path.resolve() if path.is_absolute() else (self.cwd / path).resolve()

		if self.restrict_to_cwd and not self._is_within_cwd(resolved):
			return ToolResult(success=False, error="Path is outside the current working directory")

		try:
			if not resolved.exists():
				return ToolResult(success=False, error=f"Directory not found: {raw_path}")
			if not resolved.is_dir():
				return ToolResult(success=False, error=f"Not a directory: {raw_path}")
			entries = sorted(os_name for os_name in resolved.iterdir())
			# Use Path.name for display; mark directories with trailing /
			lines = []
			for entry in entries:
				name = entry.name
				if entry.is_dir():
					name = f"{name}/"
				lines.append(name)
			output = "\n".join(lines) if lines else "(empty)"
			logger.info("[list_dir] %s -> %d entries", resolved, len(lines))
			return ToolResult(
				success=True,
				output=output,
				metadata={"path": str(resolved), "count": len(lines)},
			)
		except Exception as exc:
			logger.exception("[list_dir] Failed for %s", raw_path)
			return ToolResult(success=False, error=str(exc))

	def _is_within_cwd(self, path: Path) -> bool:
		try:
			path.relative_to(self.cwd)
			return True
		except ValueError:
			return False
