# -*- coding: utf-8 -*-
"""Unit tests for missing-binary detection and install consent flow."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from libs.deps.missing_binary import (
	KNOWN_BINARIES,
	detect_missing_binary,
	format_install_hints,
	is_missing_binary_error,
)
from libs.deps.install_flow import HandleResult, MissingBinaryHandler


class TestMissingBinaryDetection(unittest.TestCase):
	def test_detects_ffmpeg_command_not_found(self):
		err = "ffmpeg: command not found"
		self.assertTrue(is_missing_binary_error(err))
		hit = detect_missing_binary(err)
		self.assertIsNotNone(hit)
		self.assertEqual(hit.name, "ffmpeg")

	def test_detects_ffmpeg_filenotfound(self):
		err = "[WinError 2] The system cannot find the file specified: 'ffmpeg'"
		hit = detect_missing_binary(err)
		self.assertIsNotNone(hit)
		self.assertEqual(hit.name, "ffmpeg")

	def test_detects_not_recognized_windows(self):
		err = "'ffmpeg' is not recognized as an internal or external command"
		hit = detect_missing_binary(err)
		self.assertIsNotNone(hit)
		self.assertEqual(hit.name, "ffmpeg")

	def test_no_false_positive_on_unrelated_error(self):
		err = "ValueError: invalid codec name"
		self.assertFalse(is_missing_binary_error(err))
		self.assertIsNone(detect_missing_binary(err))

	def test_known_catalog_includes_ffmpeg(self):
		self.assertIn("ffmpeg", KNOWN_BINARIES)

	def test_format_install_hints_mentions_winget_on_windows(self):
		hit = detect_missing_binary("ffmpeg: command not found")
		hints = format_install_hints(hit, platform="win32")
		self.assertIn("winget", hints.lower())
		self.assertIn("ffmpeg", hints.lower())


class TestMissingBinaryHandler(unittest.TestCase):
	def test_declined_returns_skip_observation(self):
		handler = MissingBinaryHandler(
			confirm_fn=lambda prompt: False,
			search_fn=None,
			install_fn=None,
		)
		result = handler.handle(
			"ffmpeg: command not found",
			auto_yes=False,
			yolo=False,
		)
		self.assertIsInstance(result, HandleResult)
		self.assertFalse(result.installed)
		self.assertTrue(result.detected)
		self.assertIn("declined", result.observation.lower() or "")
		self.assertIn("ffmpeg", result.observation.lower())

	def test_approved_attempts_install(self):
		install_calls = []

		def fake_install(binary, method):
			install_calls.append((binary.name, method))
			return True, "ok"

		handler = MissingBinaryHandler(
			confirm_fn=lambda prompt: True,
			search_fn=None,
			install_fn=fake_install,
		)
		result = handler.handle(
			"'ffmpeg' is not recognized as an internal or external command",
			auto_yes=False,
			yolo=False,
		)
		self.assertTrue(result.detected)
		self.assertTrue(result.installed)
		self.assertEqual(install_calls[0][0], "ffmpeg")
		self.assertIn("installed", result.observation.lower())

	def test_yolo_without_yes_still_asks(self):
		asked = {"n": 0}

		def confirm(prompt):
			asked["n"] += 1
			return False

		handler = MissingBinaryHandler(confirm_fn=confirm)
		result = handler.handle("ffmpeg: command not found", auto_yes=False, yolo=True)
		self.assertEqual(asked["n"], 1)
		self.assertFalse(result.installed)

	def test_yolo_plus_yes_auto_approves(self):
		install_calls = []

		def fake_install(binary, method):
			install_calls.append(binary.name)
			return True, "ok"

		handler = MissingBinaryHandler(
			confirm_fn=lambda p: (_ for _ in ()).throw(AssertionError("should not ask")),
			install_fn=fake_install,
		)
		result = handler.handle(
			"ffmpeg: command not found",
			auto_yes=True,
			yolo=True,
		)
		self.assertTrue(result.installed)
		self.assertEqual(install_calls, ["ffmpeg"])

	def test_optional_web_search_enriches_hints(self):
		search = MagicMock(return_value="Install via winget install Gyan.FFmpeg")
		handler = MissingBinaryHandler(
			confirm_fn=lambda p: False,
			search_fn=search,
		)
		result = handler.handle(
			"ffmpeg: command not found",
			auto_yes=False,
			yolo=False,
			do_search=True,
		)
		search.assert_called()
		self.assertIn("winget", (result.search_notes or "").lower() + result.observation.lower())

	def test_non_missing_error_passthrough(self):
		handler = MissingBinaryHandler(confirm_fn=lambda p: True)
		result = handler.handle("SyntaxError: invalid syntax", auto_yes=False, yolo=False)
		self.assertFalse(result.detected)
		self.assertIsNone(result.binary)


if __name__ == "__main__":
	unittest.main()
