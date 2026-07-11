"""Registry for discovering and calling interpreter tools."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from libs.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
	"""
	Exposes tools as LLM-callable functions.

	Supports:
	- Native BaseTool registration (existing #205 API)
	- OpenAI function-calling schemas via ``openai_schemas()``
	- MCP-proxied tools via ``register_mcp_tools()``
	"""

	def __init__(self):
		self._tools: dict[str, BaseTool] = {}
		self._mcp_handlers: dict[str, Callable[[dict], ToolResult]] = {}
		self._mcp_schemas: list[dict] = []

	def register(self, tool: BaseTool):
		if not isinstance(tool, BaseTool):
			raise TypeError("tool must be a BaseTool")
		if not tool.name:
			raise ValueError("tool name is required")
		if tool.name in self._tools or tool.name in self._mcp_handlers:
			raise ValueError(f"Tool already registered: {tool.name}")
		self._tools[tool.name] = tool
		return tool

	def get(self, name: str):
		return self._tools.get(name)

	def call(self, name: str, input_data=None) -> ToolResult:
		"""Call a registered native or MCP tool by name."""
		input_data = input_data or {}
		if name in self._mcp_handlers:
			try:
				return self._mcp_handlers[name](input_data)
			except Exception as exc:
				logger.exception("MCP tool %s failed", name)
				return ToolResult(success=False, error=str(exc))

		tool = self.get(name)
		if tool is None:
			return ToolResult(success=False, error=f"Unknown tool: {name}")
		try:
			return tool.run(input_data)
		except Exception as exc:
			logger.exception("Tool %s failed", name)
			return ToolResult(success=False, error=str(exc))

	def dispatch(self, tool_name: str, tool_args: dict) -> ToolResult:
		"""Alias used by the autonomous agent loop (#215)."""
		return self.call(tool_name, tool_args or {})

	def list_tools(self) -> list:
		"""Return internal schema list (name / description / input_schema)."""
		schemas = [tool.schema() for tool in self._tools.values()]
		schemas.extend(self._mcp_internal_schemas())
		return schemas

	def openai_schemas(self) -> list[dict]:
		"""Return OpenAI-compatible function-calling tool schemas."""
		result = []
		for tool in self._tools.values():
			result.append(self._to_openai_schema(tool.name, tool.description, tool.input_schema or {}))
		result.extend(self._mcp_schemas)
		return result

	# Back-compat alias matching the issue sketch
	@property
	def TOOL_SCHEMAS(self) -> list[dict]:
		return self.openai_schemas()

	def register_mcp_tools(
		self,
		openai_schemas: list[dict],
		call_fn: Callable[[str, dict], str],
	) -> None:
		"""
		Register MCP-discovered tools.

		Args:
			openai_schemas: OpenAI function-calling schemas from MCPClient.list_tools()
			call_fn: Callable(name, arguments) -> result text (sync wrapper OK)
		"""
		for schema in openai_schemas or []:
			fn = schema.get("function") or {}
			name = fn.get("name")
			if not name:
				continue
			if name in self._tools or name in self._mcp_handlers:
				logger.warning("[ToolRegistry] Skipping duplicate MCP tool: %s", name)
				continue

			def _make_handler(tool_name: str) -> Callable[[dict], ToolResult]:
				def _handler(args: dict) -> ToolResult:
					try:
						text = call_fn(tool_name, args or {})
						return ToolResult(success=True, output=str(text or ""))
					except Exception as exc:
						return ToolResult(success=False, error=str(exc))

				return _handler

			self._mcp_handlers[name] = _make_handler(name)
			self._mcp_schemas.append(schema)
			logger.info("[ToolRegistry] Registered MCP tool: %s", name)

	def names(self) -> list[str]:
		return sorted(set(self._tools) | set(self._mcp_handlers))

	@staticmethod
	def _to_openai_schema(name: str, description: str, parameters: dict) -> dict:
		return {
			"type": "function",
			"function": {
				"name": name,
				"description": description or "",
				"parameters": parameters or {"type": "object", "properties": {}},
			},
		}

	def _mcp_internal_schemas(self) -> list[dict]:
		out = []
		for schema in self._mcp_schemas:
			fn = schema.get("function") or {}
			out.append(
				{
					"name": fn.get("name", ""),
					"description": fn.get("description", ""),
					"input_schema": fn.get("parameters") or {},
				}
			)
		return out

	def __repr__(self):
		tool_names = ", ".join(self.names())
		return f"ToolRegistry(tools=[{tool_names}])"
