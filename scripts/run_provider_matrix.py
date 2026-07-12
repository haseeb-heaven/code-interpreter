#!/usr/bin/env python3
"""CLI: live provider × mode × language matrix.

Usage (PowerShell):
  $env:LIVE_MATRIX = "1"
  $env:INTERPRETER_TEST_DATA_DIR = "D:\\tmp"
  D:\\henv\\Scripts\\python.exe scripts/run_provider_matrix.py

Never prints API key values. Soft-skips missing keys/runtimes/quota.
Exit 1 only when hard FAILs remain.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)


def main() -> int:
	parser = argparse.ArgumentParser(description="Live provider/mode/language matrix")
	parser.add_argument(
		"--report-dir",
		default=str(ROOT / "scratch" / "provider_matrix_reports"),
		help="Directory for JSON/MD reports",
	)
	parser.add_argument(
		"--python",
		default=sys.executable,
		help="Python executable for CLI smoke subprocesses",
	)
	parser.add_argument("--llm-only", action="store_true", help="Only run llm_ping cases")
	parser.add_argument("--classic-only", action="store_true", help="Only run classic_smoke cases")
	parser.add_argument("--agentic-only", action="store_true", help="Only run agentic_smoke cases")
	parser.add_argument("-v", "--verbose", action="store_true")
	args = parser.parse_args()

	logging.basicConfig(
		level=logging.DEBUG if args.verbose else logging.INFO,
		format="%(levelname)s %(message)s",
	)

	from tests.live.matrix_runner import run_matrix

	only: set[str] | None = None
	if args.llm_only:
		only = {"llm_ping"}
	elif args.classic_only:
		only = {"classic_smoke"}
	elif args.agentic_only:
		only = {"agentic_smoke"}

	result = run_matrix(
		report_dir=Path(args.report_dir),
		python_exe=args.python,
		only_kinds=only,
	)
	summary = result["summary"]
	print("\n=== PROVIDER MATRIX SUMMARY ===")
	print(
		f"PASS={summary['PASS']} SKIP={summary['SKIP']} "
		f"FAIL={summary['FAIL']} TOTAL={summary['TOTAL']}"
	)
	print("Providers (names only):")
	for p in result["providers"]:
		if p["source"] in ("family", "local"):
			print(f"  {p['id']}: {'PRESENT' if p['available'] else 'ABSENT'} -> {p['config']}")
	print("Runtimes:")
	for lang, info in result["runtimes"].items():
		print(f"  {lang}: {'OK' if info.get('available') else 'MISSING'}")
	print("Report:", result["report_paths"].get("latest") or result["report_paths"].get("markdown"))
	for row in result["rows"]:
		print(f"[{row['status']:4}] {row['id']}: {row['detail']}")
	return 1 if summary["FAIL"] else 0


if __name__ == "__main__":
	raise SystemExit(main())
