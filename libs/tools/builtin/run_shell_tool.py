"""Built-in tool for running shell commands."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from libs.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class RunShellTool(BaseTool):
	"""Run a shell command and return combined stdout/stderr."""

	name = "run_shell"
	description = "Run a shell command and return stdout + stderr. Use for git, grep, find, etc."
	input_schema = {
		"type": "object",
		"properties": {
			"command": {"type": "string", "description": "The shell command to execute."},
			"timeout": {
				"type": "integer",
				"description": "Timeout in seconds. Default 30.",
				"default": 30,
			},
		},
		"required": ["command"],
	}

	def __init__(self, cwd=None, default_timeout: int = 30):
		self.cwd = Path(cwd or Path.cwd()).resolve()
		self.default_timeout = default_timeout

	def run(self, input_data):
		command = (input_data or {}).get("command")
		if not command or not str(command).strip():
			return ToolResult(success=False, error="command is required")

		timeout = int((input_data or {}).get("timeout", self.default_timeout) or self.default_timeout)
		logger.info("[run_shell] cmd=%r timeout=%s cwd=%s", command, timeout, self.cwd)

		try:
			result = subprocess.run(
				str(command),
				shell=True,
				capture_output=True,
				text=True,
				timeout=timeout,
				cwd=str(self.cwd),
			)
			output = (result.stdout or "") + (result.stderr or "")
			return ToolResult(
				success=result.returncode == 0,
				output=output,
				error="" if result.returncode == 0 else f"exit code {result.returncode}",
				metadata={"returncode": result.returncode, "command": str(command)},
			)
		except subprocess.TimeoutExpired:
			return ToolResult(
				success=False,
				output="",
				error=f"Command timed out after {timeout}s",
			)
		except Exception as exc:
			logger.exception("[run_shell] Failed")
			return ToolResult(success=False, error=str(exc))
