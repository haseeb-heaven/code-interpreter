"""Built-in tool for executing generated code."""

from __future__ import annotations

from libs.tools.base_tool import BaseTool, ToolResult


class CodeExecutionTool(BaseTool):
	name = "execute_code"
	description = "Execute code in a supported interpreter language."
	input_schema = {
		"type": "object",
		"properties": {
			"code": {"type": "string", "description": "Code to execute."},
			"language": {"type": "string", "enum": ["python", "javascript"], "default": "python"},
		},
		"required": ["code"],
	}

	def __init__(self, executor):
		self.executor = executor

	def run(self, input_data):
		code = input_data.get("code", "")
		language = input_data.get("language", "python")
		output, error = self.executor.execute_code(code, language, force_execute=True)
		return ToolResult(success=not bool(error), output=output or "", error=error or "")
