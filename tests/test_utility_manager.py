"""Expanded unit tests for UtilityManager helpers (no network)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libs.utility_manager import UtilityManager


class TestUtilityManager(unittest.TestCase):
	def setUp(self):
		self.manager = UtilityManager()

	def test_get_full_file_path_valid(self):
		valid_path = "valid_file.txt"
		expected_path = os.path.abspath(os.path.join(os.getcwd(), valid_path))
		self.assertEqual(self.manager.get_full_file_path(valid_path), expected_path)
		self.assertEqual(self.manager.get_full_file_path(expected_path), expected_path)

	def test_get_full_file_path_traversal_relative(self):
		"""Relative `..` escapes from cwd must remain blocked.

		Use ``os.sep`` so backslash paths are not treated as a single literal
		filename on POSIX (where ``\\`` is not a separator).
		"""
		escape_passwd = os.path.join("..", "etc", "passwd")
		with self.assertRaises(ValueError) as context:
			self.manager.get_full_file_path(escape_passwd)
		self.assertIn("Security Error: Path traversal attempt detected", str(context.exception))

		escape_hosts = os.path.join("..", "..", "Windows", "System32", "drivers", "etc", "hosts")
		with self.assertRaises(ValueError) as context:
			self.manager.get_full_file_path(escape_hosts)
		self.assertIn("Security Error: Path traversal attempt detected", str(context.exception))

	def test_get_full_file_path_absolute_windows_not_traversal(self):
		"""User-named Windows absolute paths are input reads, not traversal."""
		win_path = r"D:\demo\AutomatorSuitNews.jpg"
		result = self.manager.get_full_file_path(win_path)
		self.assertIsNotNone(result)
		normalized = result.replace("/", "\\")
		self.assertTrue(
			normalized.lower().endswith(r"\demo\automatorsuitnews.jpg")
			or normalized.lower() == win_path.lower(),
			msg=f"Unexpected resolved path: {result!r}",
		)

	def test_get_full_file_path_absolute_posix_allowed_for_input(self):
		"""Explicit POSIX absolute paths are allowed for prompt input-file resolution."""
		posix_path = "/tmp/demo_input.csv"
		result = self.manager.get_full_file_path(posix_path)
		self.assertIsNotNone(result)
		self.assertEqual(os.path.basename(result), "demo_input.csv")
		# On Windows 3.13+, abspath maps /tmp/... onto the current drive.
		self.assertTrue(
			"tmp" in result.replace("\\", "/").lower(),
			msg=f"Unexpected resolved path: {result!r}",
		)

	def test_get_full_file_path_absolute_disallowed_when_restricted(self):
		"""Restricted relative-only mode uses a clear sandbox error, not 'traversal'."""
		with self.assertRaises(ValueError) as context:
			self.manager.get_full_file_path(
				r"D:\demo\AutomatorSuitNews.jpg",
				allow_absolute=False,
			)
		message = str(context.exception)
		self.assertIn("Absolute paths outside sandbox not allowed", message)
		self.assertNotIn("Path traversal attempt", message)

	def test_get_full_file_path_empty(self):
		self.assertIsNone(self.manager.get_full_file_path(""))
		self.assertIsNone(self.manager.get_full_file_path(None))

	def test_extract_content_variants(self):
		self.assertEqual(self.manager._extract_content(None), "")
		self.assertEqual(self.manager._extract_content("plain"), "plain")
		obj = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="from-obj"))])
		self.assertEqual(self.manager._extract_content(obj), "from-obj")
		self.assertEqual(
			self.manager._extract_content({"choices": [{"message": {"content": "from-dict"}}]}),
			"from-dict",
		)
		self.assertEqual(self.manager._extract_content({"response": "legacy"}), "legacy")

	def test_list_available_models(self):
		with tempfile.TemporaryDirectory() as tmp:
			(Path(tmp) / "models.toml").write_text(
				'[models."gpt-4o"]\nmodel = "gpt-4o"\n\n'
				'[models."local-model"]\nmodel = "llama3.1:8b"\n',
				encoding="utf-8",
			)
			models = self.manager.list_available_models(tmp)
			self.assertEqual(models, ["gpt-4o", "local-model"])

	def test_read_config_file(self):
		from libs.core.model_registry import ModelRegistry

		with tempfile.TemporaryDirectory() as tmp:
			registry_path = os.path.join(tmp, "models.toml")
			with open(registry_path, "w", encoding="utf-8") as fh:
				fh.write('[models."gpt-4o"]\nmodel = "gpt-4o"\nprovider = "openai"\n')
			fixture_registry = ModelRegistry.load(registry_path, use_cache=False)
			with patch.object(ModelRegistry, "load", return_value=fixture_registry):
				cfg = self.manager.read_config_file("gpt-4o")
			self.assertEqual(cfg["model"], "gpt-4o")
		with self.assertRaises(ValueError):
			self.manager.read_config_file(None)

	def test_read_config_file_accepts_legacy_json_path(self):
		from libs.core.model_registry import ModelRegistry

		with tempfile.TemporaryDirectory() as tmp:
			registry_path = os.path.join(tmp, "models.toml")
			with open(registry_path, "w", encoding="utf-8") as fh:
				fh.write('[models."gpt-4o"]\nmodel = "gpt-4o"\n')
			fixture_registry = ModelRegistry.load(registry_path, use_cache=False)
			with patch.object(ModelRegistry, "load", return_value=fixture_registry):
				cfg = self.manager.read_config_file("configs/gpt-4o.json")
			self.assertEqual(cfg["model"], "gpt-4o")

	def test_extract_file_name(self):
		self.assertEqual(self.manager.extract_file_name("open data.csv please"), "data.csv")
		self.assertIsNone(self.manager.extract_file_name("no file here"))
		self.assertIsNone(self.manager.extract_file_name("run script.exe now"))

	def test_get_os_platform(self):
		name, version = self.manager.get_os_platform()
		self.assertTrue(name)
		self.assertTrue(version)

	def test_display_help_and_version(self):
		with patch("libs.utility_manager.display_markdown_message") as display:
			self.manager.display_help()
			self.manager.display_version("9.9.9")
			joined = " ".join(str(c.args[0]) for c in display.call_args_list)
			self.assertIn("/exit", joined)
			self.assertIn("9.9.9", joined)

	def test_file_io_helpers(self):
		with tempfile.TemporaryDirectory() as tmp:
			path = os.path.join(tmp, "note.txt")
			self.manager.create_file(path)
			self.manager.write_file(path, "hello")
			self.assertEqual(self.manager.read_file(path), "hello")

	def test_read_csv_headers(self):
		with tempfile.TemporaryDirectory() as tmp:
			path = os.path.join(tmp, "a.csv")
			with open(path, "w", encoding="utf-8", newline="") as fh:
				fh.write("a,b,c\n1,2,3\n")
			self.assertEqual(self.manager.read_csv_headers(path), ["a", "b", "c"])
			empty = os.path.join(tmp, "empty.csv")
			open(empty, "w", encoding="utf-8").close()
			self.assertEqual(self.manager.read_csv_headers(empty), [])

	def test_get_output_history(self):
		with tempfile.TemporaryDirectory() as tmp:
			out_dir = os.path.join(tmp, "output")
			os.makedirs(out_dir)
			fname = os.path.join(out_dir, "code_2020_01_01-00_00_00.py")
			with open(fname, "w", encoding="utf-8") as fh:
				fh.write("print(1)")
			cwd = os.getcwd()
			try:
				os.chdir(tmp)
				path, code = self.manager.get_output_history(mode="code", language="python")
				self.assertTrue(path.endswith(".py"))
				self.assertEqual(code, "print(1)")
			finally:
				os.chdir(cwd)

	@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False)
	def test_get_default_model_name(self):
		self.assertEqual(UtilityManager.get_default_model_name(), "gpt-4o")

	@patch("requests.get")
	def test_download_file(self, get_mock):
		resp = MagicMock()
		resp.content = b"abc"
		resp.raise_for_status = MagicMock()
		get_mock.return_value = resp
		with tempfile.TemporaryDirectory() as tmp:
			dest = os.path.join(tmp, "req.txt")
			self.assertTrue(UtilityManager._download_file("https://example.com/x", dest))
			with open(dest, "rb") as fh:
				self.assertEqual(fh.read(), b"abc")


if __name__ == "__main__":
	unittest.main()
