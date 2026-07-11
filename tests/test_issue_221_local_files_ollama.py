# -*- coding: utf-8 -*-
"""Integration / interactive tests for Issue #221 (attach + ollama flags).

Uses --yes / INTERPRETER_YES=1. Soft-skips live billing. Never logs secrets.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
	lower = (output or "").lower()
	for snippet in (
		"openai_api_key=",
		"anthropic_api_key=",
		"gemini_api_key=",
		"groq_api_key=",
		"-----begin",
	):
		unittest.TestCase().assertNotIn(snippet, lower)


class TestIssue221CliFlags(unittest.TestCase):
	def test_help_documents_attach_ollama_local(self):
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
		out = proc.stdout
		self.assertIn("--attach", out)
		self.assertIn("--ollama", out)
		self.assertIn("--local", out)
		self.assertIn("--list-ollama", out)
		_assert_no_secrets(out)

	def test_parser_attach_keeps_prompt_file_flag(self):
		import interpreter as mod

		parser = mod.build_parser()
		args = parser.parse_args(
			["--attach", "a.csv", "b.json", "-f", "prompt.txt", "--cli"]
		)
		self.assertEqual(args.attach, ["a.csv", "b.json"])
		self.assertEqual(args.file, "prompt.txt")

	@patch("libs.local.ollama_helper.resolve_ollama_model", return_value="llama3:8b")
	def test_prepare_args_ollama_sets_local_model(self, _resolve):
		import interpreter as mod

		parser = mod.build_parser()
		args = parser.parse_args(["--ollama", "llama3", "--cli"])
		prepared = mod.prepare_args(args, ["interpreter.py", "--ollama", "llama3", "--cli"])
		self.assertEqual(prepared.model, "local-model")
		self.assertEqual(prepared.ollama_model_name, "llama3:8b")
		self.assertTrue(prepared.local)

	@patch("libs.local.ollama_helper.resolve_ollama_model", return_value="mistral")
	def test_prepare_args_local_implies_ollama(self, resolve_mock):
		import interpreter as mod

		parser = mod.build_parser()
		args = parser.parse_args(["--local", "--cli"])
		prepared = mod.prepare_args(args, ["interpreter.py", "--local", "--cli"])
		resolve_mock.assert_called()
		self.assertEqual(prepared.ollama_model_name, "mistral")
		self.assertTrue(prepared.local)


class TestAttachInteractive(unittest.TestCase):
	def test_cli_file_commands_piped_stdin(self):
		"""Pipe /file commands without AUTO_YES so stdin is actually read."""
		with tempfile.TemporaryDirectory() as tmp:
			csv_path = Path(tmp) / "data.csv"
			csv_path.write_text("x,y\n1,2\n", encoding="utf-8")
			env = os.environ.copy()
			# Do not set INTERPRETER_YES/CI — those force AUTO_YES defaults of /exit.
			env.pop("INTERPRETER_YES", None)
			env.pop("CI", None)
			env["CODE_INTERPRETER_HOME"] = tmp
			script = f"/file {csv_path}\n/files\n/clear-files\n/exit\n"
			proc = subprocess.run(
				[
					PYTHON,
					str(ROOT / "interpreter.py"),
					"--cli",
					"-m",
					"local-model",
					"--output-format",
					"plain",
					"--no-color",
				],
				cwd=str(ROOT),
				input=script,
				capture_output=True,
				text=True,
				timeout=90,
				env=env,
			)
			combined = proc.stdout + proc.stderr
			_soft_skip_if_billing(combined)
			_assert_no_secrets(combined)
			self.assertIn("Attached", combined)
			self.assertIn("data.csv", combined)
			self.assertIn("Cleared all attached files", combined)


if __name__ == "__main__":
	unittest.main()
