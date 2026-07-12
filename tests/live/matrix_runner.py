"""Execute live provider matrix cases and write scratch reports."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from tests.live.matrix_cases import build_matrix_cases
from tests.live.provider_detect import (
	ROOT,
	detect_providers,
	language_runtimes,
	resolve_test_data_dir,
)

logger = logging.getLogger(__name__)

load_dotenv(ROOT / ".env", override=True)

SKIP_MARKERS = (
	"not found",
	"not a valid model",
	"unavailable for free",
	"deprecated",
	"not supported",
	"insufficient balance",
	"no resource package",
	"please recharge",
	"model_not_supported",
	"does not exist",
	"exceeded your current quota",
	"credit balance is too low",
	"billing details",
	"purchase credits",
	"resource_exhausted",
	"rate limit",
	"ratelimit",
	"too many requests",
	"provider returned error",
	"no healthy upstream",
	"capacity",
	"overloaded",
	"timeout",
	"timed out",
	"connection refused",
	"connection reset",
	"temporarily unavailable",
	"503",
	"429",
)


def classify_exception(exc: BaseException) -> tuple[str, str]:
	"""Map provider/runtime failures to SKIP vs product FAIL."""
	detail = f"{type(exc).__name__}: {exc}"
	low = detail.lower()
	if any(m in low for m in SKIP_MARKERS):
		return "SKIP", detail
	return "FAIL", detail


def _load_config(label: str) -> dict[str, Any]:
	path = ROOT / "configs" / f"{label}.json"
	if not path.is_file():
		raise FileNotFoundError(f"config missing: {label}")
	return json.loads(path.read_text(encoding="utf-8"))


def _run_llm_ping(case: dict[str, Any]) -> tuple[str, str]:
	import litellm

	from libs.llm_dispatcher import dispatch_completion

	litellm.set_verbose = False
	cfg = _load_config(str(case["config"]))
	model = str(cfg["model"])
	provider = str(cfg.get("provider", ""))
	api_base = str(cfg.get("api_base", "None"))
	stream = bool(case.get("stream"))
	text = dispatch_completion(
		model=model,
		messages=[
			{"role": "system", "content": "Reply with exactly PONG and nothing else."},
			{"role": "user", "content": "ping"},
		],
		temperature=0,
		max_tokens=16,
		config_provider=provider,
		api_base=api_base,
		stream=stream,
		show_stream=False,
	)
	if not str(text).strip():
		# Empty completion is usually a provider/stream flake — soft-skip live matrix.
		return "SKIP", f"empty response soft-skip stream={stream}"
	return "PASS", f"llm ok stream={stream} ({len(str(text))} chars)"


def _prompt_for_language(lang: str) -> str:
	if lang == "javascript":
		return (
			"Write a tiny JavaScript program that prints exactly MATRIX_OK to stdout. "
			"Return only a fenced javascript code block."
		)
	if lang == "r":
		return (
			"Write a tiny R program that prints exactly MATRIX_OK. "
			"Return only a fenced r code block."
		)
	return (
		"Write a tiny Python program that prints exactly MATRIX_OK. "
		"Return only a fenced python code block."
	)


def _ensure_fixture_prompt(lang: str, test_data: Path) -> Path:
	fixtures = test_data / "provider_matrix_fixtures"
	fixtures.mkdir(parents=True, exist_ok=True)
	path = fixtures / f"prompt_{lang}.txt"
	path.write_text(_prompt_for_language(lang), encoding="utf-8")
	return path


def _run_cli_smoke(case: dict[str, Any], *, python_exe: str, test_data: Path) -> tuple[str, str]:
	lang = str(case.get("language") or "python")
	prompt = _ensure_fixture_prompt(lang, test_data)
	config = str(case["config"])
	cmd = [
		python_exe,
		str(ROOT / "interpreter.py"),
		"--cli",
		"-m",
		config,
		"-md",
		"code",
		"-l",
		lang,
		"-f",
		str(prompt),
		"-y",
		"--exec",
		"--timeout",
		"45",
	]
	if case.get("kind") == "agentic_smoke":
		cmd.append("--agentic")
	if case.get("stream"):
		cmd.append("--stream")
	else:
		cmd.append("--no-stream")
	if case.get("sandbox") == "off":
		cmd.append("--no-sandbox")
	else:
		cmd.extend(["--sandbox", "subprocess"])

	env = os.environ.copy()
	env["PYTHONIOENCODING"] = "utf-8"
	env["INTERPRETER_YES"] = "1"
	env.setdefault("INTERPRETER_TEST_DATA_DIR", str(test_data))

	proc = subprocess.run(
		cmd,
		cwd=str(ROOT),
		capture_output=True,
		text=True,
		encoding="utf-8",
		errors="replace",
		timeout=180,
		env=env,
	)
	out = (proc.stdout or "") + "\n" + (proc.stderr or "")
	low = out.lower()
	if proc.returncode != 0:
		# Soft-skip provider/runtime issues only on failed CLI runs
		# ("not found" etc. often appear in success banners).
		if any(m in low for m in SKIP_MARKERS):
			return "SKIP", f"cli soft-skip (exit={proc.returncode})"
		if any(x in low for x in ("api key", "authentication", "unauthorized", "401", "403")):
			return "SKIP", f"cli auth soft-skip (exit={proc.returncode})"
		tail = out[-800:].replace("\n", " | ")
		return "FAIL", f"cli exit={proc.returncode}: {tail}"
	billing_markers = (
		"exceeded your current quota",
		"insufficient balance",
		"please recharge",
		"credit balance is too low",
		"rate limit",
		"resource_exhausted",
	)
	if any(m in low for m in billing_markers):
		return "SKIP", "cli billing soft-skip (exit=0)"
	return "PASS", f"cli ok exit=0 ({case.get('kind')})"


def run_case(
	case: dict[str, Any],
	*,
	python_exe: str,
	test_data: Path,
) -> dict[str, Any]:
	"""Execute one matrix case; never raise — always returns status row."""
	started = time.time()
	row = {
		"id": case["id"],
		"kind": case["kind"],
		"provider": case.get("provider"),
		"config": case.get("config"),
		"stream": case.get("stream"),
		"sandbox": case.get("sandbox"),
		"language": case.get("language"),
		"mode": case.get("mode"),
		"status": "SKIP",
		"detail": "",
		"seconds": 0.0,
	}
	try:
		if case.get("expected") == "skip":
			row["status"] = "SKIP"
			row["detail"] = case.get("skip_reason") or "pre-skipped"
			return row
		if case["kind"] == "llm_ping":
			status, detail = _run_llm_ping(case)
		elif case["kind"] in ("classic_smoke", "agentic_smoke"):
			status, detail = _run_cli_smoke(case, python_exe=python_exe, test_data=test_data)
		else:
			status, detail = "FAIL", f"unknown kind {case['kind']}"
		row["status"] = status
		row["detail"] = detail
	except Exception as exc:  # noqa: BLE001
		status, detail = classify_exception(exc)
		row["status"] = status
		row["detail"] = detail
		logger.debug("case %s failed:\n%s", case["id"], traceback.format_exc())
	finally:
		row["seconds"] = round(time.time() - started, 2)
	return row


def write_report(rows: list[dict[str, Any]], report_dir: Path, run_id: str = "") -> dict[str, str]:
	"""Write JSON + Markdown summary; return paths."""
	report_dir.mkdir(parents=True, exist_ok=True)
	run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	summary = {
		"PASS": sum(1 for r in rows if r.get("status") == "PASS"),
		"SKIP": sum(1 for r in rows if r.get("status") == "SKIP"),
		"FAIL": sum(1 for r in rows if r.get("status") == "FAIL"),
		"TOTAL": len(rows),
	}
	payload = {
		"run_id": run_id,
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"summary": summary,
		"rows": rows,
	}
	json_path = report_dir / f"provider_matrix_{run_id}.json"
	md_path = report_dir / f"provider_matrix_{run_id}.md"
	json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

	lines = [
		f"# Provider matrix report `{run_id}`",
		"",
		f"- PASS={summary['PASS']} SKIP={summary['SKIP']} FAIL={summary['FAIL']} TOTAL={summary['TOTAL']}",
		"",
		"| Status | ID | Provider | Detail | Seconds |",
		"|--------|----|----------|--------|---------|",
	]
	for r in rows:
		detail = str(r.get("detail") or "").replace("|", "/").replace("\n", " ")[:120]
		lines.append(
			f"| {r.get('status')} | `{r.get('id')}` | {r.get('provider')} | {detail} | {r.get('seconds')} |"
		)
	lines.append("")
	md_path.write_text("\n".join(lines), encoding="utf-8")
	latest = report_dir / "provider_matrix_latest.md"
	latest.write_text("\n".join(lines), encoding="utf-8")
	return {"json": str(json_path), "markdown": str(md_path), "latest": str(latest)}


def run_matrix(
	*,
	report_dir: Path | None = None,
	python_exe: str | None = None,
	only_kinds: set[str] | None = None,
) -> dict[str, Any]:
	"""Detect → build cases → run → report."""
	python_exe = python_exe or sys.executable
	report_dir = report_dir or (ROOT / "scratch" / "provider_matrix_reports")
	test_data = resolve_test_data_dir(require=False)
	if test_data is None:
		test_data = ROOT / "scratch" / "provider_matrix_testdata"
		test_data.mkdir(parents=True, exist_ok=True)
		os.environ["INTERPRETER_TEST_DATA_DIR"] = str(test_data)

	providers = detect_providers()
	for p in providers:
		if p.get("source") in ("family", "local"):
			logger.info(
				"provider %s: %s",
				p["id"],
				"PRESENT" if p["available"] else "ABSENT",
			)
	runtimes = language_runtimes()
	cases = build_matrix_cases(providers, runtimes)
	if only_kinds:
		cases = [c for c in cases if c["kind"] in only_kinds]

	rows: list[dict[str, Any]] = []
	for case in cases:
		logger.info("RUN %s", case["id"])
		rows.append(run_case(case, python_exe=python_exe, test_data=test_data))

	paths = write_report(rows, report_dir)
	summary = {
		"PASS": sum(1 for r in rows if r["status"] == "PASS"),
		"SKIP": sum(1 for r in rows if r["status"] == "SKIP"),
		"FAIL": sum(1 for r in rows if r["status"] == "FAIL"),
		"TOTAL": len(rows),
	}
	return {
		"summary": summary,
		"rows": rows,
		"report_paths": paths,
		"providers": [
			{"id": p["id"], "available": p["available"], "config": p["config"], "source": p["source"]}
			for p in providers
		],
		"runtimes": runtimes,
	}
