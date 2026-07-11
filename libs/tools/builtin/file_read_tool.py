"""Built-in tool for reading local files."""

from __future__ import annotations

from pathlib import Path

from libs.tools.base_tool import BaseTool, ToolResult


class FileReadTool(BaseTool):
	name = "read_file"
	description = "Read a UTF-8 text file with a maximum output size."
	input_schema = {
		"type": "object",
		"properties": {
			"path": {"type": "string", "description": "File path to read."},
			"max_chars": {"type": "integer", "default": 100000},
		},
		"required": ["path"],
	}

	def __init__(self, cwd=None, max_chars=100_000, restrict_to_cwd=False):
		self.cwd = Path(cwd or Path.cwd()).resolve()
		self.max_chars = max_chars
		self.restrict_to_cwd = restrict_to_cwd

	def run(self, input_data):
		raw_path = input_data.get("path")
		if not raw_path:
			return ToolResult(success=False, error="path is required")

		max_chars = int(input_data.get("max_chars", self.max_chars))
		path = Path(raw_path)
		resolved_path = path.resolve() if path.is_absolute() else (self.cwd / path).resolve()

		if self.restrict_to_cwd and not self._is_within_cwd(resolved_path):
			return ToolResult(success=False, error="Path is outside the current working directory")
		if not resolved_path.is_file():
			return ToolResult(success=False, error=f"File not found: {raw_path}")

		with resolved_path.open("r", encoding="utf-8") as file:
			content = file.read(max_chars + 1)

		truncated = len(content) > max_chars
		output = content[:max_chars]
		return ToolResult(
			success=True,
			output=output,
			metadata={
				"path": str(resolved_path),
				"truncated": truncated,
				"max_chars": max_chars,
			},
		)

	def _is_within_cwd(self, path: Path) -> bool:
		try:
			path.relative_to(self.cwd)
			return True
		except ValueError:
			return False
