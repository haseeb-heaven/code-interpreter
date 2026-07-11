"""Helpers for constructing the default tool registry."""

from __future__ import annotations

from libs.tools.builtin import (
	CodeExecutionTool,
	FileReadTool,
	FileWriteTool,
	GlobSearchTool,
	ListDirTool,
	PackageInstallTool,
	RunShellTool,
)
from libs.tools.tool_registry import ToolRegistry


def build_registry(executor, package_manager, *, include_native_fs: bool = True) -> ToolRegistry:
	"""
	Build the default tool registry.

	Args:
		executor: Code execution backend for CodeExecutionTool.
		package_manager: Package manager for PackageInstallTool.
		include_native_fs: When True (default), register FS/shell autonomy tools (#215).
	"""
	registry = ToolRegistry()
	registry.register(CodeExecutionTool(executor))
	registry.register(PackageInstallTool(package_manager))
	registry.register(FileReadTool())
	if include_native_fs:
		registry.register(FileWriteTool())
		registry.register(ListDirTool())
		registry.register(RunShellTool())
		registry.register(GlobSearchTool())
	return registry


def build_native_fs_registry(cwd=None, restrict_to_cwd: bool = False) -> ToolRegistry:
	"""Registry with only the five native FS/shell tools from issue #215."""
	registry = ToolRegistry()
	registry.register(FileReadTool(cwd=cwd, restrict_to_cwd=restrict_to_cwd))
	registry.register(FileWriteTool(cwd=cwd, restrict_to_cwd=restrict_to_cwd))
	registry.register(ListDirTool(cwd=cwd, restrict_to_cwd=restrict_to_cwd))
	registry.register(RunShellTool(cwd=cwd))
	registry.register(GlobSearchTool(cwd=cwd))
	return registry
