"""TC006 — Full project unittest suite stays green (regression gate)."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TC006_Full_Unittest_Suite_Passes(unittest.TestCase):
	def test_unittest_discover(self):
		result = subprocess.run(
			[sys.executable, "-m", "unittest", "discover", "-s", "tests"],
			cwd=ROOT,
			capture_output=True,
			text=True,
			timeout=180,
		)
		self.assertEqual(
			result.returncode,
			0,
			msg=(result.stdout or "")[-2000:] + "\n" + (result.stderr or "")[-2000:],
		)


if __name__ == "__main__":
	unittest.main()
