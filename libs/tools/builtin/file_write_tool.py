"""Built-in tool for writing local files."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from libs.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class FileWriteTool(BaseTool):
	"""Write or overwrite UTF-8 text to a file (creates parent dirs)."""

	name = "write_file"
	description = "Write or overwrite content to a file. Creates parent dirs if missing."
	input_schema = {
		"type": "object",
		"properties": {
			"path": {"type": "string", "description": "Absolute or relative path to the file."},
			"content": {"type": "string", "description": "Text content to write."},
		},
		"required": ["path", "content"],
	}

	def __init__(self, cwd=None, restrict_to_cwd: bool = False):
		self.cwd = Path(cwd or Path.cwd()).resolve()
		self.restrict_to_cwd = restrict_to_cwd

	def run(self, input_data):
		raw_path = input_data.get("path")
		content = input_data.get("content")
		if not raw_path:
			return ToolResult(success=False, error="path is required")
		if content is None:
			return ToolResult(success=False, error="content is required")

		path = Path(str(raw_path))
		resolved = path.resolve() if path.is_absolute() else (self.cwd / path).resolve()

		if self.restrict_to_cwd and not self._is_within_cwd(resolved):
			return ToolResult(success=False, error="Path is outside the current working directory")

		try:
			os.makedirs(resolved.parent, exist_ok=True)
			resolved.write_text(str(content), encoding="utf-8")
			logger.info("[write_file] Wrote %s (%d chars)", resolved, len(str(content)))
			return ToolResult(
				success=True,
				output=f"Written to {resolved}",
				metadata={"path": str(resolved), "bytes": len(str(content).encode("utf-8"))},
			)
		except Exception as exc:
			logger.exception("[write_file] Failed for %s", raw_path)
			return ToolResult(success=False, error=str(exc))

	def _is_within_cwd(self, path: Path) -> bool:
		try:
			path.relative_to(self.cwd)
			return True
		except ValueError:
			return False
