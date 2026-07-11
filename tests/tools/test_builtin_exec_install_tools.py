"""Unit tests for built-in package install and code execution tools."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from libs.tools.builtin.code_execution_tool import CodeExecutionTool
from libs.tools.builtin.package_install_tool import PackageInstallTool


class TestPackageInstallTool(unittest.TestCase):
	def test_requires_name(self):
		tool = PackageInstallTool(MagicMock())
		result = tool.run({"language": "python"})
		self.assertFalse(result.success)
		self.assertIn("name", result.error.lower())

	def test_install_success(self):
		pm = MagicMock()
		tool = PackageInstallTool(pm)
		result = tool.run({"name": "rich", "language": "python"})
		self.assertTrue(result.success)
		pm.install_package.assert_called_once_with("rich", "python")
		self.assertEqual(result.metadata["package"], "rich")

	def test_install_failure(self):
		pm = MagicMock()
		pm.install_package.side_effect = ValueError("missing")
		tool = PackageInstallTool(pm)
		result = tool.run({"name": "nope"})
		self.assertFalse(result.success)
		self.assertIn("missing", result.error)


class TestCodeExecutionTool(unittest.TestCase):
	def test_execute_success(self):
		executor = MagicMock()
		executor.execute_code.return_value = ("ok", None)
		tool = CodeExecutionTool(executor)
		result = tool.run({"code": "print(1)", "language": "python"})
		self.assertTrue(result.success)
		self.assertEqual(result.output, "ok")
		executor.execute_code.assert_called_once_with("print(1)", "python", force_execute=True)

	def test_execute_error(self):
		executor = MagicMock()
		executor.execute_code.return_value = (None, "boom")
		tool = CodeExecutionTool(executor)
		result = tool.run({"code": "bad"})
		self.assertFalse(result.success)
		self.assertEqual(result.error, "boom")


if __name__ == "__main__":
	unittest.main()
