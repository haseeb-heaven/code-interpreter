"""Built-in tool for installing missing packages."""

from __future__ import annotations

from libs.tools.base_tool import BaseTool, ToolResult


class PackageInstallTool(BaseTool):
	name = "install_package"
	description = "Install a package for a supported language."
	input_schema = {
		"type": "object",
		"properties": {
			"name": {"type": "string", "description": "Package name to install."},
			"language": {"type": "string", "enum": ["python", "javascript"], "default": "python"},
		},
		"required": ["name"],
	}

	def __init__(self, package_manager):
		self.package_manager = package_manager

	def run(self, input_data):
		package_name = input_data.get("name", "")
		language = input_data.get("language", "python")
		if not package_name:
			return ToolResult(success=False, error="name is required")

		try:
			self.package_manager.install_package(package_name, language)
			return ToolResult(
				success=True,
				output=f"Installed package {package_name} for {language}.",
				metadata={"package": package_name, "language": language},
			)
		except Exception as exc:
			return ToolResult(success=False, error=str(exc), metadata={"package": package_name, "language": language})
