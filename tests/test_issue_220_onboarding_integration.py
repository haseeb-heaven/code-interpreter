# -*- coding: utf-8 -*-
"""Integration + interactive tests for Issue #220 onboarding / --free tip.

Uses ``--yes`` / ``INTERPRETER_YES=1`` so prompts never hang.
Live LLM calls soft-skip on billing/quota. Never prints secrets.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

_QUOTA_MARKERS = (
	"rate limit",
	"quota",
	"billing",
	"insufficient_quota",
	"429",
	"resource_exhausted",
	"credit",
	"payment required",
)


def _soft_skip_if_billing(output: str) -> None:
	lower = (output or "").lower()
	if any(m in lower for m in _QUOTA_MARKERS):
		raise unittest.SkipTest(f"Soft-skip live billing/quota: {output[:160]}")


def _assert_no_secrets(output: str) -> None:
	"""Fail if common secret patterns appear in CLI output."""
	lower = (output or "").lower()
	# Never assert raw env values; only check that we did not dump .env contents.
	forbidden_snippets = (
		"openai_api_key=",
		"anthropic_api_key=",
		"gemini_api_key=",
		"groq_api_key=",
		"-----begin",
	)
	for snippet in forbidden_snippets:
		unittest.TestCase().assertNotIn(snippet, lower, "CLI must not log secrets")


class TestFreeTipIntegration(unittest.TestCase):
	"""--list-free tip line points at --free (Issue #220)."""

	def test_list_free_tip_uses_free_flag(self):
		env = os.environ.copy()
		env["INTERPRETER_YES"] = "1"
		env["CI"] = "1"
		proc = subprocess.run(
			[PYTHON, str(ROOT / "interpreter.py"), "--list-free"],
			cwd=str(ROOT),
			capture_output=True,
			text=True,
			timeout=60,
			env=env,
		)
		self.assertEqual(proc.returncode, 0, proc.stderr)
		out = proc.stdout + proc.stderr
		_assert_no_secrets(out)
		self.assertIn('--free "describe your task here"', out)
		self.assertNotIn("--gemini-style -m <config>", out)


class TestFirstRunWelcomeInteractive(unittest.TestCase):
	"""CLI first-run welcome with redirected home + --yes."""

	def test_cli_shows_welcome_once_with_yes(self):
		with tempfile.TemporaryDirectory() as tmp:
			env = os.environ.copy()
			env["INTERPRETER_YES"] = "1"
			env["CI"] = "1"
			env["CODE_INTERPRETER_HOME"] = tmp
			# Do not copy or print .env secrets into assertions.
			proc = subprocess.run(
				[
					PYTHON,
					str(ROOT / "interpreter.py"),
					"--cli",
					"--yes",
					"-m",
					"local-model",
					"--output-format",
					"plain",
				],
				cwd=str(ROOT),
				input="/exit\n",
				capture_output=True,
				text=True,
				timeout=90,
				env=env,
			)
			combined = proc.stdout + proc.stderr
			_soft_skip_if_billing(combined)
			_assert_no_secrets(combined)
			# Welcome should appear on first run (before /exit).
			self.assertIn("Code Interpreter - Free & Local", combined, combined[:800])
			self.assertIn("/free", combined)
			sentinel = Path(tmp) / ".code_interpreter_welcomed"
			self.assertTrue(sentinel.exists(), f"missing sentinel in {tmp}")

			# Second run: sentinel present → no welcome banner.
			proc2 = subprocess.run(
				[
					PYTHON,
					str(ROOT / "interpreter.py"),
					"--cli",
					"--yes",
					"-m",
					"local-model",
					"--output-format",
					"plain",
				],
				cwd=str(ROOT),
				input="/exit\n",
				capture_output=True,
				text=True,
				timeout=90,
				env=env,
			)
			combined2 = proc2.stdout + proc2.stderr
			_soft_skip_if_billing(combined2)
			_assert_no_secrets(combined2)
			self.assertNotIn(
				"+==========================================================+",
				combined2,
				combined2[:800],
			)

	def test_json_one_shot_skips_welcome_noise(self):
		"""Structured / file one-shots should not spam the welcome box.

		Welcome gating runs before Interpreter boot / any LLM call. Use a
		missing model config so the process fails fast offline instead of
		hanging on retries to localhost:11434 (no Ollama/stub in CI).
		"""
		with tempfile.TemporaryDirectory() as tmp:
			task = Path(tmp) / "task.txt"
			task.write_text("print(1)\n", encoding="utf-8")
			env = os.environ.copy()
			env["INTERPRETER_YES"] = "1"
			env["CI"] = "1"
			env["CODE_INTERPRETER_HOME"] = tmp
			proc = subprocess.run(
				[
					PYTHON,
					str(ROOT / "interpreter.py"),
					"--cli",
					"--yes",
					"-m",
					"nonexistent-model-ci-no-llm",
					"-f",
					str(task),
					"--output-format",
					"json",
				],
				cwd=str(ROOT),
				capture_output=True,
				text=True,
				timeout=60,
				env=env,
			)
			combined = proc.stdout + proc.stderr
			_soft_skip_if_billing(combined)
			_assert_no_secrets(combined)
			self.assertNotIn("Code Interpreter - Free & Local", combined)
			self.assertNotIn("+==========================================================+", combined)


class TestFreeFlagHelpSurface(unittest.TestCase):
	def test_help_documents_free(self):
		env = os.environ.copy()
		env["INTERPRETER_YES"] = "1"
		proc = subprocess.run(
			[PYTHON, str(ROOT / "interpreter.py"), "--help"],
			cwd=str(ROOT),
			capture_output=True,
			text=True,
			timeout=60,
			env=env,
		)
		self.assertEqual(proc.returncode, 0, proc.stderr)
		self.assertIn("--free", proc.stdout)
		_assert_no_secrets(proc.stdout + proc.stderr)


if __name__ == "__main__":
	unittest.main()
