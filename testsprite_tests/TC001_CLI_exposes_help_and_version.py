"""TC001 — CLI exposes help and version (backend/CLI integration)."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TC001_CLI_Help_And_Version(unittest.TestCase):
	def test_help_documents_agent_flag(self):
		result = subprocess.run(
			[sys.executable, str(ROOT / "interpreter.py"), "--help"],
			cwd=ROOT,
			capture_output=True,
			text=True,
			timeout=60,
		)
		self.assertEqual(result.returncode, 0, result.stderr)
		combined = (result.stdout or "") + (result.stderr or "")
		self.assertIn("--agent", combined)
		self.assertIn("--cli", combined)

	def test_version_prints(self):
		result = subprocess.run(
			[sys.executable, str(ROOT / "interpreter.py"), "--version"],
			cwd=ROOT,
			capture_output=True,
			text=True,
			timeout=60,
		)
		self.assertEqual(result.returncode, 0, result.stderr)
		combined = (result.stdout or "") + (result.stderr or "")
		self.assertRegex(combined, r"\d+\.\d+")


if __name__ == "__main__":
	unittest.main()
