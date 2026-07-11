"""Registry for discovering and calling interpreter tools."""

from __future__ import annotations

from libs.tools.base_tool import BaseTool, ToolResult


class ToolRegistry:
	def __init__(self):
		self._tools = {}

	def register(self, tool: BaseTool):
		if not isinstance(tool, BaseTool):
			raise TypeError("tool must be a BaseTool")
		if not tool.name:
			raise ValueError("tool name is required")
		if tool.name in self._tools:
			raise ValueError(f"Tool already registered: {tool.name}")
		self._tools[tool.name] = tool
		return tool

	def get(self, name: str):
		return self._tools.get(name)

	def call(self, name: str, input_data=None) -> ToolResult:
		tool = self.get(name)
		if tool is None:
			return ToolResult(success=False, error=f"Unknown tool: {name}")
		try:
			return tool.run(input_data or {})
		except Exception as exc:
			return ToolResult(success=False, error=str(exc))

	def list_tools(self) -> list:
		return [tool.schema() for tool in self._tools.values()]

	def __repr__(self):
		tool_names = ", ".join(sorted(self._tools))
		return f"ToolRegistry(tools=[{tool_names}])"
