# -*- coding: utf-8 -*-
"""Unit tests for Issue #220 identity / first-run onboarding."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from libs.onboarding import (
	FIRST_RUN_WELCOME,
	WELCOME_SENTINEL_NAME,
	has_seen_welcome,
	mark_welcome_seen,
	maybe_show_first_run_welcome,
	welcome_sentinel_path,
)


class TestOnboardingWelcome(unittest.TestCase):
	"""First-run welcome banner + sentinel file behavior."""

	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.home = Path(self._tmpdir.name)

	def tearDown(self):
		self._tmpdir.cleanup()

	def test_welcome_text_mentions_free_and_examples(self):
		self.assertIn("Code Interpreter - Free & Local", FIRST_RUN_WELCOME)
		self.assertIn("/free", FIRST_RUN_WELCOME)
		self.assertIn("/help", FIRST_RUN_WELCOME)
		self.assertIn("analyze data.csv", FIRST_RUN_WELCOME)

	def test_sentinel_path_uses_home(self):
		path = welcome_sentinel_path(self.home)
		self.assertEqual(path, self.home / WELCOME_SENTINEL_NAME)

	def test_show_once_then_skip(self):
		printed = []
		shown = maybe_show_first_run_welcome(
			self.home, print_fn=printed.append
		)
		self.assertTrue(shown)
		self.assertEqual(len(printed), 1)
		self.assertIn("Free & Local", printed[0])
		self.assertIn("Code Interpreter - Free & Local", printed[0])
		self.assertTrue(has_seen_welcome(self.home))

		printed.clear()
		shown_again = maybe_show_first_run_welcome(
			self.home, print_fn=printed.append
		)
		self.assertFalse(shown_again)
		self.assertEqual(printed, [])

	def test_force_reshows_welcome(self):
		mark_welcome_seen(self.home)
		printed = []
		shown = maybe_show_first_run_welcome(
			self.home, force=True, print_fn=printed.append
		)
		self.assertTrue(shown)
		self.assertEqual(len(printed), 1)

	def test_code_interpreter_home_env_override(self):
		with patch.dict(os.environ, {"CODE_INTERPRETER_HOME": str(self.home)}):
			path = welcome_sentinel_path()
			self.assertEqual(path.parent, self.home)
			self.assertTrue(maybe_show_first_run_welcome(print_fn=lambda *_: None))
			self.assertTrue((self.home / WELCOME_SENTINEL_NAME).exists())

	def test_never_logs_secrets_in_welcome(self):
		# Guardrail: welcome banner must not embed env / key material.
		forbidden = (
			"API_KEY",
			"sk-",
			".env",
			"OPENAI",
			"password",
			"secret",
		)
		lower = FIRST_RUN_WELCOME.lower()
		for token in forbidden:
			self.assertNotIn(token.lower(), lower, f"welcome leaked {token!r}")


class TestPyPIDescription(unittest.TestCase):
	"""PyPI / packaging metadata must be searchable (Issue #220)."""

	def test_pyproject_description_keywords(self):
		root = Path(__file__).resolve().parents[1]
		text = (root / "pyproject.toml").read_text(encoding="utf-8")
		lower = text.lower()
		# Case-insensitive: PyPI search is not case-sensitive.
		for needle in (
			"code interpreter",
			"chatgpt",
			"free",
			"local",
			"open interpreter",
		):
			self.assertIn(needle, lower, f"missing searchable term {needle!r}")

	def test_readme_hero_positioning(self):
		root = Path(__file__).resolve().parents[1]
		text = (root / "README.md").read_text(encoding="utf-8")
		self.assertIn("Code Interpreter — Free, Local, Any Model", text)
		self.assertIn('--free "analyze', text)
		self.assertIn("Why not Open Interpreter?", text)
		self.assertIn("Abandoned (Apr 2025)", text)


if __name__ == "__main__":
	unittest.main()
