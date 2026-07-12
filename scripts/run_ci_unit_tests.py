#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run ``unittest discover`` in fresh processes to stay under CI memory limits.

GitHub-hosted runners (~7GB) still SIGKILL/SIGXCPU ``test_unit_coverage_*``
when those three modules load together. Run each coverage file alone; keep
other cohorts batched.
"""

from __future__ import annotations

import subprocess
import sys


# Fresh process per entry. Patterns use unittest discover -p; exact filenames
# isolate the memory-heavy coverage push modules.
_BATCHES = (
	"test_[a-d]*.py",
	"test_[e-m]*.py",
	"test_[n-s]*.py",
	"test_t*.py",
	"test_unit_coverage_gaps.py",
	"test_unit_coverage_gaps2.py",
	"test_unit_coverage_push80.py",
	"test_u[!n]*.py",
	"test_[v-z]*.py",
)


def main() -> int:
	failed = False
	for pattern in _BATCHES:
		print(f"=== unittest discover -s tests -p {pattern!r} ===", flush=True)
		result = subprocess.run(
			[
				sys.executable,
				"-m",
				"unittest",
				"discover",
				"-s",
				"tests",
				"-p",
				pattern,
			],
			check=False,
		)
		if result.returncode != 0:
			failed = True
			print(
				f"Batch {pattern!r} failed with exit code {result.returncode}",
				flush=True,
			)
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
