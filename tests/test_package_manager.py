"""Unit tests for PackageManager helpers (network/subprocess mocked)."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from libs.package_manager import PackageManager


class TestPackageManager(unittest.TestCase):
	def setUp(self):
		self.pm = PackageManager()

	def test_extract_python_package_name(self):
		name = self.pm.extract_package_name(
			"ModuleNotFoundError: No module named 'requests'",
			"python",
		)
		self.assertEqual(name, "requests")

	def test_extract_javascript_package_name(self):
		name = self.pm.extract_package_name(
			"Error: Cannot find module 'lodash'\n    at ...",
			"javascript",
		)
		self.assertEqual(name, "lodash")

	def test_extract_invalid_language(self):
		with self.assertRaises(ValueError):
			self.pm.extract_package_name("x", "ruby")

	def test_get_system_modules(self):
		mods = self.pm.get_system_modules()
		self.assertIsInstance(mods, list)
		self.assertIn("os", mods)

	@patch.object(PackageManager, "_check_package_exists_pip", return_value=True)
	@patch.object(PackageManager, "_is_package_installed", return_value=True)
	def test_install_python_already_installed(self, _installed, _exists):
		self.pm.install_package("requests", "python")

	@patch.object(PackageManager, "_check_package_exists_pip", return_value=True)
	@patch.object(PackageManager, "_is_package_installed", return_value=False)
	@patch.object(PackageManager, "_install_package_with_pip")
	def test_install_python_via_pip(self, install_pip, _installed, _exists):
		self.pm.install_package("rich", "python")
		install_pip.assert_called_once_with("rich")

	@patch.object(PackageManager, "_check_package_exists_npm", return_value=True)
	@patch.object(PackageManager, "_is_package_installed", return_value=False)
	@patch.object(PackageManager, "_install_package_with_npm")
	def test_install_javascript_via_npm(self, install_npm, _installed, _exists):
		self.pm.install_package("lodash", "javascript")
		install_npm.assert_called_once_with("lodash")

	def test_install_invalid_language(self):
		with self.assertRaises(ValueError):
			self.pm.install_package("x", "go")

	@patch("libs.package_manager.requests.get")
	def test_check_package_exists_pip(self, get_mock):
		resp = MagicMock()
		resp.status_code = 200
		get_mock.return_value = resp
		self.assertTrue(self.pm._check_package_exists_pip("requests"))

	@patch("libs.package_manager.subprocess.check_call", side_effect=subprocess.CalledProcessError(1, "pip"))
	def test_is_package_installed_false(self, _check):
		self.assertFalse(self.pm._is_package_installed("nope-package", "pip"))

	@patch.object(PackageManager, "_check_package_exists_pip", return_value=True)
	@patch.object(PackageManager, "_is_package_installed", return_value=False)
	@patch.object(
		PackageManager,
		"_install_package_with_pip",
		side_effect=subprocess.CalledProcessError(1, "pip"),
	)
	@patch.object(PackageManager, "_install_package_with_pip3")
	def test_install_python_falls_back_to_pip3(self, pip3, _pip, _installed, _exists):
		self.pm.install_package("rich", "python")
		pip3.assert_called_once_with("rich")

	@patch.object(PackageManager, "_check_package_exists_pip", return_value=False)
	def test_install_python_missing_on_pypi(self, _exists):
		with self.assertRaises(ValueError):
			self.pm.install_package("definitely-missing-xyz", "python")

	@patch("libs.package_manager.requests.get")
	def test_check_package_exists_npm(self, get_mock):
		resp = MagicMock()
		resp.status_code = 200
		get_mock.return_value = resp
		self.assertTrue(self.pm._check_package_exists_npm("lodash"))
		resp.status_code = 404
		self.assertFalse(self.pm._check_package_exists_npm("nope"))

	@patch("libs.package_manager.subprocess.check_call")
	def test_is_package_installed_npm_true(self, check_call):
		check_call.return_value = 0
		self.assertTrue(self.pm._is_package_installed("lodash", "npm"))

	def test_is_package_installed_invalid_manager(self):
		with self.assertRaises(ValueError):
			self.pm._is_package_installed("x", "cargo")

	def test_extract_python_package_name_missing(self):
		with self.assertRaises(ValueError):
			self.pm._extract_python_package_name("some unrelated error")

	@patch.object(PackageManager, "_run_command")
	def test_install_helpers(self, run_cmd):
		run_cmd.return_value = 0
		self.pm._install_package_with_pip("requests")
		self.pm._install_package_with_pip3("requests")
		self.pm._install_package_with_npm("lodash")
		self.assertEqual(run_cmd.call_count, 3)


if __name__ == "__main__":
	unittest.main()
