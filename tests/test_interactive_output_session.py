"""Interactive / live soft-skip tests for #219 and #218.

Uses ``--yes`` / ``INTERPRETER_YES=1`` so prompts never hang. Live LLM calls
soft-skip on billing/quota/rate-limit. Never prints secrets.
"""

from __future__ import annotations

import json
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


def _has_any_provider_key() -> bool:
	keys = (
		"OPENAI_API_KEY",
		"ANTHROPIC_API_KEY",
		"GEMINI_API_KEY",
		"GOOGLE_API_KEY",
		"GROQ_API_KEY",
		"OPENROUTER_API_KEY",
		"DEEPSEEK_API_KEY",
	)
	return any(os.environ.get(k) for k in keys)


def _looks_like_quota(text: str) -> bool:
	lower = (text or "").lower()
	return any(m in lower for m in _QUOTA_MARKERS)


class TestInteractiveCliCommands(unittest.TestCase):
	"""Simulate REPL-style command paths without a live LLM."""

	def test_help_and_list_sessions_as_user(self):
		env = os.environ.copy()
		env["INTERPRETER_YES"] = "1"
		env["CI"] = "1"
		# --list-sessions exits before Interpreter boot
		proc = subprocess.run(
			[PYTHON, str(ROOT / "interpreter.py"), "--list-sessions"],
			cwd=str(ROOT),
			capture_output=True,
			text=True,
			timeout=60,
			env=env,
		)
		self.assertEqual(proc.returncode, 0, proc.stderr)
		out = proc.stdout + proc.stderr
		self.assertTrue(
			"No saved sessions" in out or "SESSION ID" in out,
			out[:500],
		)

	def test_output_format_json_flag_in_help_path(self):
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
		self.assertEqual(proc.returncode, 0)
		out = proc.stdout
		self.assertIn("--output-format", out)
		self.assertIn("json", out)
		self.assertIn("markdown", out)
		self.assertIn("plain", out)

	def test_session_roundtrip_via_store_cli_delete(self):
		"""Create a session file, list it, delete it — mimicking user workflow."""
		from libs.memory.session_store import SessionStore

		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			store = SessionStore("interactive-demo", session_dir=root)
			store.save(
				[{"user": "hello", "assistant": {"task": "hello"}, "system": {}}],
				model="local-model",
			)
			listed = SessionStore.list_sessions(session_dir=root)
			self.assertEqual(listed[0]["session_id"], "interactive-demo")
			self.assertTrue(SessionStore.delete_session("interactive-demo", session_dir=root))
			self.assertEqual(SessionStore.list_sessions(session_dir=root), [])


@unittest.skipUnless(_has_any_provider_key(), "No provider API keys in environment")
class TestLiveStructuredOutputSoftSkip(unittest.TestCase):
	"""Optional live smoke: JSON output with --yes. Soft-skip quota/billing."""

	def test_live_json_one_shot_if_keys(self):
		with tempfile.TemporaryDirectory() as tmp:
			task = Path(tmp) / "task.txt"
			task.write_text("Reply with a single word: pong", encoding="utf-8")
			env = os.environ.copy()
			env["INTERPRETER_YES"] = "1"
			env["CI"] = "1"
			# Prefer free/local-ish if configured; otherwise whatever -m resolves
			cmd = [
				PYTHON,
				str(ROOT / "interpreter.py"),
				"--cli",
				"--yes",
				"--no-stream",
				"--output-format",
				"json",
				"-md",
				"chat",
				"-f",
				str(task),
			]
			# Use free catalog preference when possible without printing keys
			if os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GROQ_API_KEY"):
				cmd.extend(["--free"])
			proc = subprocess.run(
				cmd,
				cwd=str(ROOT),
				capture_output=True,
				text=True,
				timeout=120,
				env=env,
			)
			combined = proc.stdout + proc.stderr
			if _looks_like_quota(combined):
				self.skipTest("Provider quota/rate-limit — soft-skipped")
			if proc.returncode != 0:
				# Soft-skip auth/config failures that are not assertion bugs
				if any(
					x in combined.lower()
					for x in (".env", "api key", "authentication", "unauthorized", "not setup")
				):
					self.skipTest("Provider/auth unavailable — soft-skipped")
				self.fail(f"live run failed rc={proc.returncode}: {combined[:800]}")
			# Try to parse JSON from stdout (may have leading banners if plain leak)
			text = proc.stdout.strip()
			try:
				# Find first JSON object
				start = text.find("{")
				end = text.rfind("}")
				self.assertGreaterEqual(start, 0, text[:400])
				payload = json.loads(text[start : end + 1])
				self.assertIn("status", payload)
				self.assertIn("result", payload)
			except json.JSONDecodeError:
				if _looks_like_quota(combined):
					self.skipTest("Provider quota — soft-skipped")
				self.fail(f"Expected JSON output, got: {text[:500]}")


if __name__ == "__main__":
	unittest.main()
