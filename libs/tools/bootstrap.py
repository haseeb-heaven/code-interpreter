"""Helpers for constructing the default tool registry."""

from __future__ import annotations

from libs.tools.builtin import CodeExecutionTool, FileReadTool, PackageInstallTool
from libs.tools.tool_registry import ToolRegistry


def build_registry(executor, package_manager) -> ToolRegistry:
	registry = ToolRegistry()
	registry.register(CodeExecutionTool(executor))
	registry.register(PackageInstallTool(package_manager))
	registry.register(FileReadTool())
	return registry
