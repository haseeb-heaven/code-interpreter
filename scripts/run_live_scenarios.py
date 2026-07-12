#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI: automated live user scenarios (JSON/charts/paths/agentic/slash).

Usage (PowerShell)::

    $env:INTERPRETER_TEST_DATA_DIR = "D:\\tmp"   # never hardcode in tests
    $env:INTERPRETER_YES = "1"
    D:\\henv\\Scripts\\python.exe scripts/run_live_scenarios.py --tier easy

Exit 1 only when FAIL > 0 (SKIP is OK). Reports under scratch/.
Never prints API key values.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
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
		help="Directory for JSON/MD/HTML reports (gitignored scratch/)",
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
		"--offline-only",
		action="store_true",
		help="Policy + offline + offline_exec only (no live LLM)",
	)
	parser.add_argument(
		"--merge-report",
		action="store_true",
		help="Merge rows into existing live_scenario_report.json in report-dir",
	)
	parser.add_argument(
		"--tier",
		action="append",
		choices=("easy", "medium"),
		help="Filter tiers (repeatable)",
	)
	parser.add_argument(
		"--easy-report",
		action="store_true",
		help="Also write scratch/easy_scenarios_report.md (+ .html)",
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
	if args.policy_only or args.offline_only:
		models = [pick_default_model()]
	elif all_models:
		models = [m["config"] for m in available_models_one_by_one()] or [pick_default_model()]
	else:
		models = [pick_default_model()]

	tiers = set(args.tier) if args.tier else None
	# Default: when only --tier easy, also emit easy report copy
	easy_report = args.easy_report or (tiers == {"easy"})

	result = run_suite(
		report_dir=Path(args.report_dir),
		python_exe=args.python,
		models=models,
		tiers=tiers,
		policy_only=args.policy_only,
		offline_only=args.offline_only,
		merge_report=args.merge_report,
	)
	summary = result["summary"]
	print("\n=== LIVE SCENARIOS SUMMARY ===")
	print(
		f"PASS={summary['PASS']} SKIP={summary['SKIP']} "
		f"FAIL={summary['FAIL']} TOTAL={summary['TOTAL']}"
	)
	print(f"Models: {', '.join(result.get('models') or [])}")
	print(f"Report: {result.get('report_md')}")

	if easy_report:
		scratch = ROOT / "scratch"
		scratch.mkdir(parents=True, exist_ok=True)
		md_src = Path(result["report_md"])
		html_src = Path(result["report_html"])
		md_dst = scratch / "easy_scenarios_report.md"
		html_dst = scratch / "easy_scenarios_report.html"
		# Rewrite title for easy partial report
		text = md_src.read_text(encoding="utf-8")
		text = text.replace("# Live scenario report", "# Easy live scenarios report", 1)
		md_dst.write_text(text, encoding="utf-8")
		if html_src.is_file():
			html = html_src.read_text(encoding="utf-8")
			html = html.replace("Live scenario report", "Easy live scenarios report", 1)
			html_dst.write_text(html, encoding="utf-8")
		print(f"Easy report: {md_dst}")
		result["easy_report_md"] = str(md_dst)
		result["easy_report_html"] = str(html_dst)

	if summary["FAIL"]:
		print("\nFailures:")
		for row in result["rows"]:
			if row.get("status") == "FAIL":
				print(f"  - {row['id']}: {row.get('detail')}")
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
