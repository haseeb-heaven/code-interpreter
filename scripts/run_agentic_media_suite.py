#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run agentic media live suite (Approach A) one case at a time.

Writes markdown + JSON reports under ``scratch/agentic_media_reports/``.

Usage (PowerShell)::

    $env:INTERPRETER_TEST_DATA_DIR = "D:\\tmp"   # shell env only — never hardcoded
    $env:INTERPRETER_YES = "1"
    D:\\henv\\Scripts\\python.exe scripts/run_agentic_media_suite.py

Canonical env: INTERPRETER_TEST_DATA_DIR (alias: TEST_DATA_DIR).
Never prints API key values. Soft-skips billing/quota/auth and missing deps.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

from tests.agentic.media.cases import build_cases
from tests.agentic.media.fixtures import TestDataDirError, ensure_media_fixtures, resolve_test_data_dir
from tests.agentic.media.runner import pick_default_model, run_case
from tests.agentic.media.soft_skip import redact_output

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("agentic_media_suite")

REPORT_ROOT = ROOT / "scratch" / "agentic_media_reports"

_KEY_NAMES = (
	"OPENAI_API_KEY",
	"ANTHROPIC_API_KEY",
	"GEMINI_API_KEY",
	"GROQ_API_KEY",
	"OPENROUTER_API_KEY",
	"HUGGINGFACE_API_KEY",
)


def _key_presence_summary() -> list[dict[str, str]]:
	rows = []
	for name in _KEY_NAMES:
		val = (os.getenv(name) or "").strip()
		status = "PRESENT" if val and len(val) >= 16 else "ABSENT"
		rows.append({"key": name, "status": status})
	return rows


def _runtime_flags() -> dict[str, bool]:
	import shutil

	return {
		"python": True,
		"javascript": bool(shutil.which("node")),
		"r": bool(shutil.which("Rscript") or shutil.which("R")),
		"ffmpeg": bool(shutil.which("ffmpeg")),
	}


def _write_reports(stamp: str, payload: dict) -> tuple[Path, Path]:
	REPORT_ROOT.mkdir(parents=True, exist_ok=True)
	json_path = REPORT_ROOT / f"report_{stamp}.json"
	md_path = REPORT_ROOT / f"report_{stamp}.md"
	# Redact any accidental secrets in excerpts
	safe_payload = json.loads(redact_output(json.dumps(payload)))
	json_path.write_text(json.dumps(safe_payload, indent=2), encoding="utf-8")

	lines = [
		f"# Agentic media suite report ({stamp})",
		"",
		f"- Default model: `{payload.get('default_model')}`",
		f"- Test data dir: `{payload.get('test_data_dir')}`",
		f"- Duration s: {payload.get('duration_s')}",
		"",
		"## Key presence (names only)",
		"",
		"| Key | Status |",
		"|-----|--------|",
	]
	for row in payload.get("keys", []):
		lines.append(f"| {row['key']} | {row['status']} |")
	lines.extend(["", "## Runtimes", ""])
	for k, v in (payload.get("runtimes") or {}).items():
		lines.append(f"- `{k}`: {'yes' if v else 'no'}")
	lines.extend(
		[
			"",
			"## Results",
			"",
			"| Tier | ID | Status | Model | Seconds | Reason |",
			"|------|----|--------|-------|---------|--------|",
		]
	)
	for r in payload.get("results", []):
		reason = (r.get("reason") or "").replace("|", "/")[:80]
		lines.append(
			f"| {r.get('tier')} | {r.get('id')} | {r.get('status')} | "
			f"{r.get('model')} | {r.get('duration_s')} | {reason} |"
		)
	counts = payload.get("counts") or {}
	lines.extend(
		[
			"",
			"## Summary",
			"",
			f"- PASS: **{counts.get('PASS', 0)}**",
			f"- FAIL: **{counts.get('FAIL', 0)}**",
			f"- SKIP: **{counts.get('SKIP', 0)}**",
			"",
		]
	)
	md_path.write_text("\n".join(lines), encoding="utf-8")
	latest = REPORT_ROOT / "report_latest.md"
	latest.write_text("\n".join(lines), encoding="utf-8")
	return json_path, md_path


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Agentic media live suite runner")
	parser.add_argument("--tier", choices=("easy", "medium", "complex", "all"), default="all")
	parser.add_argument("--quick", action="store_true", help="Run only easy tier + first medium")
	parser.add_argument("--model", default=None, help="Override model for cases without one")
	parser.add_argument("--stop-on-fail", action="store_true")
	parser.add_argument("--max-cases", type=int, default=0, help="Cap cases (0 = no cap)")
	args = parser.parse_args(argv)

	try:
		data_dir = resolve_test_data_dir(require=True)
	except TestDataDirError as exc:
		logger.error("%s", exc)
		return 2

	fixtures = ensure_media_fixtures(data_dir)
	cases = build_cases(fixtures=fixtures)
	if args.tier != "all":
		cases = [c for c in cases if c.tier == args.tier]
	if args.quick:
		easy = [c for c in cases if c.tier == "easy"]
		med = [c for c in cases if c.tier == "medium"][:1]
		cases = easy + med
	if args.max_cases and args.max_cases > 0:
		cases = cases[: args.max_cases]

	default_model = args.model or pick_default_model()
	logger.info("Cases=%d default_model=%s data_dir=%s", len(cases), default_model, data_dir)

	started = datetime.now(timezone.utc)
	results = []
	for case in cases:
		logger.info("=== %s [%s/%s] ===", case.id, case.tier, case.category)
		try:
			res = run_case(case, model_override=case.model or default_model)
		except Exception as exc:  # noqa: BLE001
			res = {
				"id": case.id,
				"tier": case.tier,
				"category": case.category,
				"status": "FAIL",
				"reason": f"runner exception: {type(exc).__name__}",
				"duration_s": 0,
				"model": case.model or default_model,
				"output_excerpt": redact_output(traceback.format_exc()[-1500:]),
			}
		results.append(res)
		logger.info("-> %s %s (%s)", res["status"], case.id, res.get("reason"))
		if args.stop_on_fail and res["status"] == "FAIL":
			break

	ended = datetime.now(timezone.utc)
	counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
	for r in results:
		counts[r["status"]] = counts.get(r["status"], 0) + 1

	stamp = started.strftime("%Y%m%d_%H%M%S")
	payload = {
		"stamp": stamp,
		"started": started.isoformat(),
		"ended": ended.isoformat(),
		"duration_s": round((ended - started).total_seconds(), 2),
		"default_model": default_model,
		"test_data_dir": str(data_dir),
		"fixture_dir": fixtures.get("fixture_dir"),
		"keys": _key_presence_summary(),
		"runtimes": _runtime_flags(),
		"counts": counts,
		"results": results,
	}
	json_path, md_path = _write_reports(stamp, payload)
	logger.info("Report JSON: %s", json_path)
	logger.info("Report MD:   %s", md_path)
	logger.info("Summary PASS=%s FAIL=%s SKIP=%s", counts["PASS"], counts["FAIL"], counts["SKIP"])
	return 1 if counts.get("FAIL", 0) else 0


if __name__ == "__main__":
	raise SystemExit(main())
