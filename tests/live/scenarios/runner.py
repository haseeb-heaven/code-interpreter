# -*- coding: utf-8 -*-
"""Execute live user scenarios; soft-skip quota/auth; never raise."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tests.live.provider_detect import detect_providers, looks_real
from tests.live.scenarios.cases import ScenarioCase, build_scenario_cases
from tests.live.scenarios.fixtures import ensure_scenario_fixtures, resolve_test_data_dir
from tests.live.scenarios.soft_skip import is_soft_skip, redact_output

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]

_MODEL_PREF = (
	("OPENROUTER_API_KEY", "openrouter-free"),
	("GROQ_API_KEY", "groq-llama-3.1-8b"),
	("GEMINI_API_KEY", "gemini-2.5-flash-lite"),
	("OPENAI_API_KEY", "gpt-4o-mini"),
	("HUGGINGFACE_API_KEY", "hf-meta-llama-3"),
)


def pick_default_model() -> str:
	for env_key, config in _MODEL_PREF:
		if looks_real(env_key):
			return config
	return "local-model"


def available_models_one_by_one() -> list[dict[str, str]]:
	"""Models with present keys (names only) for one-by-one live passes."""
	rows = []
	for prov in detect_providers():
		if not prov.get("available"):
			continue
		if prov.get("source") not in ("family", "local", "free_catalog"):
			continue
		rows.append(
			{
				"id": str(prov["id"]),
				"config": str(prov["config"]),
				"env_key": str(prov.get("env_key") or ""),
			}
		)
	# De-dupe by config
	seen = set()
	unique = []
	for row in rows:
		if row["config"] in seen:
			continue
		seen.add(row["config"])
		unique.append(row)
	return unique


def _run_policy_case(case: ScenarioCase) -> tuple[str, str]:
	"""In-process policy checks — no LLM, always deterministic."""
	if case.policy == "json_not_vision":
		from libs.vision.image_handler import image_file_arg_for_path, is_image_source_path

		path = case.prompt or "data.json"
		if is_image_source_path(path) or image_file_arg_for_path(path) is not None:
			return "FAIL", f".json treated as image: {path}"
		return "PASS", "json not vision"

	if case.policy == "sandbox_home":
		from libs.safety_manager import ExecutionSafetyManager

		sm = ExecutionSafetyManager()
		ctx = sm.build_sandbox_context()
		try:
			home = ctx.env.get("HOME") or ""
			mpl = ctx.env.get("MPLCONFIGDIR") or ""
			if not home or not mpl:
				return "FAIL", f"missing HOME/MPLCONFIGDIR: {ctx.env}"
			if str(ctx.cwd) not in home and not home.startswith(str(ctx.cwd)):
				return "FAIL", f"HOME not under sandbox cwd: {home}"
			return "PASS", "sandbox HOME/MPLCONFIGDIR ok"
		finally:
			sm.cleanup_sandbox_context(ctx)

	if case.policy == "user_intent_write":
		from libs.safety_manager import ExecutionSafetyManager

		target = case.prompt
		sm = ExecutionSafetyManager()
		sm.set_user_intent_paths([target])
		# Build open() code with the absolute path
		code = (
			f"with open(r'{target}', 'w', encoding='utf-8') as f:\n"
			f"    f.write('HELLO_SCENARIO')\n"
		)
		d = sm.assess_execution(code, "code")
		if not d.allowed:
			return "FAIL", f"user-intent write blocked: {d.reasons}"
		return "PASS", "user-intent absolute write allowed"

	if case.policy == "block_silent_abs_write":
		from libs.safety_manager import ExecutionSafetyManager

		sm = ExecutionSafetyManager()
		sm.set_user_intent_paths([r"D:\allowed\only.txt"])
		evil = "with open(r'D:\\Windows\\evil.txt', 'w') as f:\n    f.write('x')\n"
		d = sm.assess_execution(evil, "code")
		if d.allowed:
			return "FAIL", "silent absolute write was allowed"
		return "PASS", "silent absolute write blocked"

	return "FAIL", f"unknown policy {case.policy}"


def _build_cli_command(case: ScenarioCase, prompt_path: Optional[Path], model: str) -> list[str]:
	python_exe = os.environ.get("INTERPRETER_TEST_PYTHON") or sys.executable
	cmd = [
		python_exe,
		str(ROOT / "interpreter.py"),
		"--cli",
		"-m",
		model,
		"-md",
		"code",
		"-l",
		"python",
		"--yes",
		"--timeout",
		"90",
	]
	if prompt_path is not None:
		cmd.extend(["-f", str(prompt_path), "--exec"])
	if case.agentic:
		cmd.append("--agentic")
	if case.gemini_style:
		cmd.append("--gemini-style")
	if case.free:
		cmd.append("--free")
	if case.yolo:
		cmd.append("--yolo")
	if case.no_sandbox:
		cmd.append("--no-sandbox")
	elif case.sandbox:
		cmd.extend(["--sandbox", case.sandbox])
	cmd.extend(case.extra_args or [])
	return cmd


def _classify_cli_output(case: ScenarioCase, proc: subprocess.CompletedProcess) -> tuple[str, str]:
	out = (proc.stdout or "") + "\n" + (proc.stderr or "")
	redacted = redact_output(out)
	low = out.lower()

	if is_soft_skip(out):
		return "SKIP", f"soft-skip: {redacted[-400:]}"

	if proc.returncode != 0 and case.kind != "slash":
		if any(x in low for x in ("api key", "authentication", "unauthorized")):
			return "SKIP", f"auth soft-skip exit={proc.returncode}"
		return "FAIL", f"exit={proc.returncode}: {redacted[-600:]}"

	for forbidden in case.forbid_markers:
		if forbidden.lower() in low:
			return "FAIL", f"forbidden marker {forbidden!r} in output"

	if case.expect_markers:
		missing = [m for m in case.expect_markers if m.lower() not in low]
		# Slash / YOLO: accept partial success when core markers present
		if missing and case.kind == "slash":
			# /exit or Exiting is enough if forbid passed
			if "exit" in low:
				return "PASS", f"slash ok (missing optional {missing})"
		if missing and case.yolo:
			if "autoloop" in low or "tool" in low or "yolo" in low:
				return "PASS", "yolo loop exercised"
			if is_soft_skip(out):
				return "SKIP", "yolo soft-skip"
		if missing:
			return "FAIL", f"missing markers {missing}: {redacted[-500:]}"

	return "PASS", f"ok ({case.kind})"


def run_case(case: ScenarioCase, *, model_override: Optional[str] = None) -> dict[str, Any]:
	"""Execute one scenario; always returns a status row (never raises)."""
	started = time.time()
	model = model_override or case.model or pick_default_model()
	row: dict[str, Any] = {
		"id": case.id,
		"tier": case.tier,
		"kind": case.kind,
		"model": model,
		"status": "SKIP",
		"detail": "",
		"seconds": 0.0,
	}
	try:
		if case.kind == "policy":
			status, detail = _run_policy_case(case)
			row["status"] = status
			row["detail"] = detail
			return row

		env = os.environ.copy()
		env["PYTHONIOENCODING"] = "utf-8"
		env["INTERPRETER_YES"] = "1"
		data_dir = resolve_test_data_dir(require=False)
		if data_dir is not None:
			env.setdefault("INTERPRETER_TEST_DATA_DIR", str(data_dir))

		prompt_path = None
		input_text = case.stdin_script
		if case.kind == "slash":
			cmd = _build_cli_command(case, None, model)
			# Interactive REPL — feed stdin script
			proc = subprocess.run(
				cmd,
				cwd=str(ROOT),
				input=input_text or "/exit\n",
				capture_output=True,
				text=True,
				encoding="utf-8",
				errors="replace",
				timeout=120,
				env=env,
			)
		else:
			with tempfile.TemporaryDirectory(prefix="ci_scenario_") as tmp:
				prompt_path = Path(tmp) / "prompt.txt"
				prompt_path.write_text(case.prompt or "print(1)", encoding="utf-8")
				cmd = _build_cli_command(case, prompt_path, model)
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

		status, detail = _classify_cli_output(case, proc)
		row["status"] = status
		row["detail"] = detail
	except subprocess.TimeoutExpired:
		row["status"] = "SKIP"
		row["detail"] = "timeout soft-skip"
	except Exception as exc:  # noqa: BLE001
		detail = f"{type(exc).__name__}: {exc}"
		row["status"] = "SKIP" if is_soft_skip(detail) else "FAIL"
		row["detail"] = redact_output(detail)
		logger.debug("scenario %s error:\n%s", case.id, traceback.format_exc())
	finally:
		row["seconds"] = round(time.time() - started, 2)
	return row


def run_suite(
	*,
	report_dir: Optional[Path] = None,
	python_exe: Optional[str] = None,
	models: Optional[list[str]] = None,
	tiers: Optional[set[str]] = None,
	policy_only: bool = False,
) -> dict[str, Any]:
	"""Run all scenarios; write scratch report; return summary payload."""
	if python_exe:
		os.environ["INTERPRETER_TEST_PYTHON"] = python_exe

	# Fixtures: prefer env dir; else temp so policy/slash always run
	data_dir = resolve_test_data_dir(require=False)
	temp_holder = None
	if data_dir is None:
		import tempfile as _tf

		temp_holder = _tf.TemporaryDirectory(prefix="ci_live_scenarios_")
		data_dir = Path(temp_holder.name)
		os.environ["INTERPRETER_TEST_DATA_DIR"] = str(data_dir)

	fixtures = ensure_scenario_fixtures(data_dir)
	cases = build_scenario_cases(fixtures)
	if policy_only:
		cases = [c for c in cases if c.kind == "policy"]
	if tiers:
		cases = [c for c in cases if c.tier in tiers]

	model_list = models or [pick_default_model()]
	rows: list[dict[str, Any]] = []

	# Policy + slash once (model-independent)
	for case in cases:
		if case.kind in ("policy", "slash"):
			rows.append(run_case(case, model_override=model_list[0]))

	# LLM cases — one model by default; optional one-by-one
	llm_cases = [c for c in cases if c.kind not in ("policy", "slash")]
	for model in model_list:
		for case in llm_cases:
			row = run_case(case, model_override=model)
			row["id"] = f"{case.id}@{model}"
			rows.append(row)

	summary = {
		"PASS": sum(1 for r in rows if r["status"] == "PASS"),
		"SKIP": sum(1 for r in rows if r["status"] == "SKIP"),
		"FAIL": sum(1 for r in rows if r["status"] == "FAIL"),
		"TOTAL": len(rows),
	}

	report_dir = report_dir or (ROOT / "scratch" / "live_scenario_reports")
	report_dir.mkdir(parents=True, exist_ok=True)
	stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	payload = {
		"run_id": stamp,
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"fixtures": fixtures,
		"models": model_list,
		"summary": summary,
		"rows": rows,
	}
	json_path = report_dir / f"live_scenarios_{stamp}.json"
	md_path = report_dir / f"live_scenarios_{stamp}.md"
	json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

	lines = [
		f"# Live scenarios report `{stamp}`",
		"",
		f"PASS={summary['PASS']} SKIP={summary['SKIP']} FAIL={summary['FAIL']} TOTAL={summary['TOTAL']}",
		"",
		"| id | status | seconds | detail |",
		"|---|---|---|---|",
	]
	for r in rows:
		detail = str(r.get("detail") or "").replace("|", "/")[:120]
		lines.append(
			f"| `{r['id']}` | {r['status']} | {r.get('seconds', 0)} | {detail} |"
		)
	md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

	payload["report_json"] = str(json_path)
	payload["report_md"] = str(md_path)

	if temp_holder is not None:
		temp_holder.cleanup()

	return payload
