# -*- coding: utf-8 -*-
"""Offline (and optional live) tests for agentic media suite — TDD.

Env:
  INTERPRETER_TEST_DATA_DIR (canonical) or TEST_DATA_DIR (alias)
  AGENTIC_MEDIA_LIVE=1 for optional live smoke
Never hardcode D:\\tmp. Never print .env secrets.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestSoftSkip(unittest.TestCase):
	def test_redact_masks_api_key_line(self):
		from tests.agentic.media.soft_skip import redact_output

		out = redact_output("OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz\nok")
		self.assertIn("[redacted", out.lower())
		self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", out)

	def test_billing_soft_skip(self):
		from tests.agentic.media.soft_skip import is_billing_or_auth_failure

		self.assertTrue(is_billing_or_auth_failure("Error 429 rate limit"))
		self.assertFalse(is_billing_or_auth_failure("DONE_CSV"))

	def test_dep_soft_skip(self):
		from tests.agentic.media.soft_skip import is_dep_or_env_failure

		self.assertTrue(is_dep_or_env_failure("ModuleNotFoundError: No module named 'x'"))
		self.assertFalse(is_dep_or_env_failure("PIPELINE_DONE"))


class TestFixtures(unittest.TestCase):
	def test_resolve_requires_env(self):
		from tests.agentic.media.fixtures import TestDataDirError, resolve_test_data_dir

		env = os.environ.copy()
		env.pop("INTERPRETER_TEST_DATA_DIR", None)
		env.pop("TEST_DATA_DIR", None)
		with patch.dict(os.environ, env, clear=True):
			with self.assertRaises(TestDataDirError):
				resolve_test_data_dir(require=True)
			self.assertIsNone(resolve_test_data_dir(require=False))

	def test_alias_and_ensure_fixtures(self):
		from tests.agentic.media.fixtures import ensure_media_fixtures, resolve_test_data_dir

		with tempfile.TemporaryDirectory() as tmp:
			with patch.dict(os.environ, {"TEST_DATA_DIR": tmp, "INTERPRETER_TEST_DATA_DIR": ""}, clear=False):
				os.environ.pop("INTERPRETER_TEST_DATA_DIR", None)
				os.environ["TEST_DATA_DIR"] = tmp
				root = resolve_test_data_dir(require=True)
				self.assertEqual(root, Path(tmp).resolve())
				meta = ensure_media_fixtures()
				paths = meta["paths"]
				for key in ("json", "png", "pdf", "wav"):
					self.assertTrue(Path(paths[key]).is_file(), key)
				self.assertIn("agentic_media_fixtures", meta["fixture_dir"])


class TestCases(unittest.TestCase):
	def test_build_cases_tiers_media_only(self):
		from tests.agentic.media.cases import build_cases
		from tests.agentic.media.fixtures import ensure_media_fixtures

		with tempfile.TemporaryDirectory() as tmp:
			with patch.dict(os.environ, {"INTERPRETER_TEST_DATA_DIR": tmp}, clear=False):
				fixtures = ensure_media_fixtures()
				cases = build_cases(fixtures=fixtures)
				tiers = {c.tier for c in cases}
				self.assertEqual(tiers, {"easy", "medium", "complex"})
				self.assertTrue(any(c.category == "media" for c in cases))
				self.assertTrue(any(c.agentic for c in cases))
				# No provider-matrix category in this package
				self.assertFalse(any(c.category == "provider" for c in cases))
				blob = " ".join(c.id for c in cases)
				self.assertIn("json", blob.lower() + " ".join(c.prompt for c in cases).lower())


class TestRunnerHelpers(unittest.TestCase):
	def test_pick_default_model_prefers_openrouter(self):
		from tests.agentic.media.runner import pick_default_model

		with patch.dict(
			os.environ,
			{
				"OPENROUTER_API_KEY": "sk-or-v1-" + ("x" * 40),
				"GROQ_API_KEY": "",
			},
			clear=False,
		):
			self.assertEqual(pick_default_model(), "openrouter-free")

	def test_build_command_agentic_and_sandbox(self):
		from tests.agentic.media.cases import SuiteCase
		from tests.agentic.media.runner import build_command

		case = SuiteCase(
			id="t",
			tier="easy",
			category="media",
			prompt="x",
			agentic=True,
			extra_args=["--no-sandbox"],
		)
		cmd = build_command(case, Path("p.txt"), "openrouter-free")
		self.assertIn("--agentic", cmd)
		self.assertIn("--no-sandbox", cmd)
		self.assertIn("--yes", cmd)


@unittest.skipUnless(os.getenv("AGENTIC_MEDIA_LIVE") == "1", "Set AGENTIC_MEDIA_LIVE=1 for live")
class TestMediaLiveOptional(unittest.TestCase):
	def test_easy_json_case(self):
		from tests.agentic.media.cases import build_cases
		from tests.agentic.media.runner import run_case

		if not (os.environ.get("INTERPRETER_TEST_DATA_DIR") or os.environ.get("TEST_DATA_DIR")):
			self.skipTest("INTERPRETER_TEST_DATA_DIR unset")
		cases = [c for c in build_cases() if "json" in c.id]
		self.assertTrue(cases)
		result = run_case(cases[0])
		if result["status"] == "SKIP":
			self.skipTest(result["reason"])
		self.assertEqual(result["status"], "PASS", result)


if __name__ == "__main__":
	unittest.main()
