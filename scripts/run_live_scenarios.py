#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI: automated live user scenarios (JSON/charts/paths/agentic/slash).

Usage (PowerShell)::

    $env:INTERPRETER_TEST_DATA_DIR = "D:\\tmp"   # never hardcode in tests
    $env:INTERPRETER_YES = "1"
    # Optional: exercise every present provider one-by-one
    $env:LIVE_SCENARIOS_ALL_MODELS = "1"
    D:\\henv\\Scripts\\python.exe scripts/run_live_scenarios.py

Exit 1 only when FAIL > 0 (SKIP is OK). Reports under scratch/live_scenario_reports/.
Never prints API key values.
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
	parser = argparse.ArgumentParser(description="Live user-scenario suite")
	parser.add_argument(
		"--report-dir",
		default=str(ROOT / "scratch" / "live_scenario_reports"),
		help="Directory for JSON/MD reports (gitignored scratch/)",
	)
	parser.add_argument(
		"--python",
		default=sys.executable,
		help="Python executable for CLI subprocesses",
	)
	parser.add_argument(
		"--all-models",
		action="store_true",
		help="Run LLM scenarios once per detected provider config",
	)
	parser.add_argument(
		"--policy-only",
		action="store_true",
		help="Only in-process policy checks (no LLM)",
	)
	parser.add_argument(
		"--tier",
		action="append",
		choices=("easy", "medium"),
		help="Filter tiers (repeatable)",
	)
	parser.add_argument("-v", "--verbose", action="store_true")
	args = parser.parse_args()

	logging.basicConfig(
		level=logging.DEBUG if args.verbose else logging.INFO,
		format="%(levelname)s %(message)s",
	)

	from tests.live.scenarios.runner import (
		available_models_one_by_one,
		pick_default_model,
		run_suite,
	)

	all_models = args.all_models or os.getenv("LIVE_SCENARIOS_ALL_MODELS", "").strip() in (
		"1",
		"true",
		"yes",
	)
	if args.policy_only:
		models = [pick_default_model()]
	elif all_models:
		models = [m["config"] for m in available_models_one_by_one()] or [pick_default_model()]
	else:
		models = [pick_default_model()]

	tiers = set(args.tier) if args.tier else None
	result = run_suite(
		report_dir=Path(args.report_dir),
		python_exe=args.python,
		models=models,
		tiers=tiers,
		policy_only=args.policy_only,
	)
	summary = result["summary"]
	print("\n=== LIVE SCENARIOS SUMMARY ===")
	print(
		f"PASS={summary['PASS']} SKIP={summary['SKIP']} "
		f"FAIL={summary['FAIL']} TOTAL={summary['TOTAL']}"
	)
	print(f"Models: {', '.join(result.get('models') or [])}")
	print(f"Report: {result.get('report_md')}")
	if summary["FAIL"]:
		print("\nFailures:")
		for row in result["rows"]:
			if row.get("status") == "FAIL":
				print(f"  - {row['id']}: {row.get('detail')}")
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
