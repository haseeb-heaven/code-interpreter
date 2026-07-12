#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run ``unittest discover`` in fresh processes to stay under CI memory limits.

GitHub-hosted runners (~7GB) OOM (exit 137/152) when the full suite loads
litellm + scientific stack into one long-lived process. Splitting by filename
pattern keeps the same coverage with lower peak RSS.
"""

from __future__ import annotations

import subprocess
import sys


# Overlapping-free partitions of top-level and nested test_*.py modules.
_PATTERNS = (
	"test_[a-d]*.py",
	"test_[e-m]*.py",
	"test_[n-s]*.py",
	"test_[t-z]*.py",
)


def main() -> int:
	failed = False
	for pattern in _PATTERNS:
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
