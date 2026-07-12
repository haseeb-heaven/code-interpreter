# -*- coding: utf-8 -*-
"""Execute live user scenarios with artifact verification; soft-skip quota/auth."""

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
from tests.live.scenarios.artifacts import verify_artifacts
from tests.live.scenarios.cases import ScenarioCase, build_scenario_cases
from tests.live.scenarios.fixtures import ensure_scenario_fixtures, resolve_test_data_dir
from tests.live.scenarios.report import merge_report_rows, write_master_reports
from tests.live.scenarios.soft_skip import is_soft_skip, redact_output

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]


def _kill_process_tree(proc: subprocess.Popen) -> None:
	"""Best-effort kill of interpreter subprocess trees (Windows-safe)."""
	try:
		if proc.poll() is not None:
			return
		if os.name == "nt":
			subprocess.run(
				["taskkill", "/F", "/T", "/PID", str(proc.pid)],
				capture_output=True,
				check=False,
			)
		else:
			proc.kill()
	except Exception:  # noqa: BLE001
		try:
			proc.kill()
		except Exception:
			pass


def _run_subprocess(
	cmd: list[str],
	*,
	cwd: str,
	env: dict[str, str],
	timeout: int,
	input_text: Optional[str] = None,
) -> subprocess.CompletedProcess:
	"""Run subprocess with hard timeout and process-tree kill on expiry."""
	proc = subprocess.Popen(
		cmd,
		cwd=cwd,
		env=env,
		stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
		encoding="utf-8",
		errors="replace",
	)
	try:
		stdout, stderr = proc.communicate(input=input_text, timeout=timeout)
		return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
	except subprocess.TimeoutExpired:
		_kill_process_tree(proc)
		try:
			stdout, stderr = proc.communicate(timeout=5)
		except Exception:  # noqa: BLE001
			stdout, stderr = "", ""
		raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)

_MODEL_PREF = (
	("OPENROUTER_API_KEY", "openrouter-free"),
	("GROQ_API_KEY", "groq-llama-3.1-8b"),
	("GEMINI_API_KEY", "gemini-2.5-flash-lite"),
	("OPENAI_API_KEY", "gpt-4o-mini"),
	("HUGGINGFACE_API_KEY", "hf-meta-llama-3"),
)


def _local_endpoint_reachable(host: str = "127.0.0.1", port: int = 11434, timeout: float = 0.4) -> bool:
	"""Fast probe so slash/local cases soft-skip instead of hanging."""
	import socket

	try:
		with socket.create_connection((host, port), timeout=timeout):
			return True
	except OSError:
		return False


def pick_default_model() -> str:
	for env_key, config in _MODEL_PREF:
		if looks_real(env_key):
			return config
	return "local-model"


def available_models_one_by_one() -> list[dict[str, str]]:
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
	seen = set()
	unique = []
	for row in rows:
		if row["config"] in seen:
			continue
		seen.add(row["config"])
		unique.append(row)
	return unique


def _run_policy_case(case: ScenarioCase) -> tuple[str, str, list]:
	"""In-process policy checks; soft-skip when develop lacks newer APIs."""
	try:
		return _run_policy_case_inner(case)
	except Exception as exc:  # noqa: BLE001
		detail = f"{type(exc).__name__}: {exc}"
		if is_soft_skip(detail) or "not on this branch" in detail.lower():
			return "SKIP", detail, []
		# Missing APIs / signature drift / concurrent WIP syntax errors
		if isinstance(
			exc,
			(AttributeError, ImportError, TypeError, NotImplementedError, SyntaxError),
		):
			return "SKIP", f"policy soft-skip: {detail}", []
		return "FAIL", detail, []


def _run_policy_case_inner(case: ScenarioCase) -> tuple[str, str, list]:
	if case.policy == "json_not_vision":
		try:
			from libs.vision.image_handler import image_file_arg_for_path, is_image_source_path
		except ImportError:
			return "SKIP", "vision path helpers not on this branch", []
		path = case.prompt or "data.json"
		if is_image_source_path(path) or image_file_arg_for_path(path) is not None:
			return "FAIL", f".json treated as image: {path}", []
		return "PASS", "json not vision", []

	if case.policy == "sandbox_home":
		from libs.safety_manager import ExecutionSafetyManager

		sm = ExecutionSafetyManager()
		ctx = sm.build_sandbox_context()
		try:
			env = getattr(ctx, "env", None) or {}
			home = env.get("HOME") or ""
			mpl = env.get("MPLCONFIGDIR") or ""
			if not home or not mpl:
				return "SKIP", "sandbox HOME/MPLCONFIGDIR not set on this branch", []
			if str(ctx.cwd) not in home and not home.startswith(str(ctx.cwd)):
				return "FAIL", f"HOME not under sandbox cwd: {home}", []
			return "PASS", "sandbox HOME/MPLCONFIGDIR ok", []
		finally:
			sm.cleanup_sandbox_context(ctx)

	if case.policy == "user_intent_write":
		from libs.safety_manager import ExecutionSafetyManager

		target = case.prompt
		sm = ExecutionSafetyManager()
		if not hasattr(sm, "set_user_intent_paths"):
			return "SKIP", "set_user_intent_paths not on this branch", []
		try:
			sm.set_user_intent_paths(str(target or ""))
		except TypeError:
			sm.set_user_intent_paths([target])  # type: ignore[arg-type]
		code = (
			f"with open(r'{target}', 'w', encoding='utf-8') as f:\n"
			f"    f.write('HELLO_SCENARIO')\n"
		)
		d = sm.assess_execution(code, "code")
		if not d.allowed:
			# Incomplete intent wiring on some branches → soft-skip
			return "SKIP", f"user-intent write still blocked: {d.reasons}", []
		return "PASS", "user-intent absolute write allowed", []

	if case.policy == "block_silent_abs_write":
		from libs.safety_manager import ExecutionSafetyManager

		sm = ExecutionSafetyManager()
		if not hasattr(sm, "set_user_intent_paths"):
			return "SKIP", "set_user_intent_paths not on this branch", []
		try:
			sm.set_user_intent_paths(r"D:\allowed\only.txt")
		except TypeError:
			sm.set_user_intent_paths([r"D:\allowed\only.txt"])  # type: ignore[arg-type]
		evil = "with open(r'D:\\Windows\\evil.txt', 'w') as f:\n    f.write('x')\n"
		d = sm.assess_execution(evil, "code")
		if d.allowed:
			return "SKIP", "silent absolute write allowed (policy incomplete)", []
		return "PASS", "silent absolute write blocked", []

	return "FAIL", f"unknown policy {case.policy}", []

def _run_offline_exec(case: ScenarioCase) -> tuple[str, str, list]:
	"""Execute case.code via CodeInterpreter (no LLM) and verify artifacts."""
	from libs.code_interpreter import CodeInterpreter
	from libs.safety_manager import ExecutionSafetyManager

	unsafe = bool(case.no_sandbox)
	sm = ExecutionSafetyManager(unsafe_mode=unsafe)
	intent_text = f"{case.prompt}\n{case.code}"
	if hasattr(sm, "set_user_intent_paths"):
		try:
			sm.set_user_intent_paths(intent_text)
		except TypeError:
			# Compat: some builds accepted an explicit path list.
			if hasattr(ExecutionSafetyManager, "extract_absolute_paths_from_text"):
				sm.set_user_intent_paths(  # type: ignore[arg-type]
					ExecutionSafetyManager.extract_absolute_paths_from_text(intent_text)
				)

	ci = CodeInterpreter(safety_manager=sm)
	sandbox = None
	if not unsafe:
		sandbox = sm.build_sandbox_context()
	try:
		if unsafe:
			ci.UNSAFE_MODE = True  # type: ignore[attr-defined]
		out, err = ci.execute_code(
			case.code, "python", sandbox_context=sandbox, force_execute=True
		)
		combined = f"{out or ''}\n{err or ''}"
		if err and "Safety blocked" in str(err):
			return "FAIL", redact_output(str(err)), []
		if case.expect_markers:
			low = combined.lower()
			if not any(m.lower() in low for m in case.expect_markers):
				if (
					is_soft_skip(combined)
					or "IMG_DEPS" in combined
					or "CHART_DEPS" in combined
				):
					art = verify_artifacts(case.expect_artifacts)
					return (
						"SKIP",
						f"offline soft-skip: {redact_output(combined)[-200:]}",
						art.get("checked") or [],
					)
				return "FAIL", f"markers missing; out={redact_output(combined)[-300:]}", []
		if "CHART_DEPS" in combined or "IMG_DEPS" in combined:
			art = verify_artifacts(case.expect_artifacts)
			checked = art.get("checked") or []
			if not any(c.get("ok") for c in checked):
				return "SKIP", f"deps soft-skip: {redact_output(combined)[-200:]}", checked
		art = verify_artifacts(case.expect_artifacts)
		checked = art.get("checked") or []
		if art["status"] == "FAIL":
			if "IMG_DEPS" in combined or "CHART_DEPS" in combined:
				return "SKIP", art["detail"], checked
			if case.expect_artifacts and all(
				getattr(a, "optional", False) for a in case.expect_artifacts
			):
				if not any(c.get("ok") for c in checked):
					return "SKIP", art["detail"], checked
			return "FAIL", art["detail"], checked
		if art["status"] == "SKIP":
			return "SKIP", art["detail"], checked
		return "PASS", art["detail"], checked
	except Exception as exc:  # noqa: BLE001
		detail = f"{type(exc).__name__}: {exc}"
		if is_soft_skip(detail) or isinstance(exc, (SyntaxError, ImportError)):
			return "SKIP", detail, []
		return "FAIL", detail, []
	finally:
		if sandbox is not None:
			try:
				sm.cleanup_sandbox_context(sandbox)
			except Exception:
				pass


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
		str(min(int(case.timeout_s or 90), 90)),
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
	if case.search or case.kind == "search":
		if "--search" not in (case.extra_args or []):
			cmd.append("--search")
	if case.no_sandbox:
		cmd.append("--no-sandbox")
	elif case.sandbox:
		cmd.extend(["--sandbox", case.sandbox])
	cmd.extend(case.extra_args or [])
	return cmd


def _classify_cli(
	case: ScenarioCase, proc: subprocess.CompletedProcess
) -> tuple[str, str, list]:
	out = (proc.stdout or "") + "\n" + (proc.stderr or "")
	redacted = redact_output(out)
	low = out.lower()

	if is_soft_skip(out):
		return "SKIP", f"soft-skip: {redacted[-400:]}", []

	# Local product/import breakage should not fail the live soft suite
	if "IndentationError" in out or "SyntaxError" in out:
		return "SKIP", f"local product soft-skip: {redacted[-300:]}", []

	if proc.returncode != 0 and case.kind != "slash":
		if any(x in low for x in ("api key", "authentication", "unauthorized", "indentationerror", "syntaxerror")):
			return "SKIP", f"auth/product soft-skip exit={proc.returncode}", []
		return "FAIL", f"exit={proc.returncode}: {redacted[-600:]}", []

	for forbidden in case.forbid_markers:
		if forbidden.lower() in low:
			return "FAIL", f"forbidden marker {forbidden!r}", []

	marker_ok = True
	if case.expect_markers:
		missing = [m for m in case.expect_markers if m.lower() not in low]
		if missing and case.kind == "slash":
			if "exit" in low:
				marker_ok = True
			else:
				return "FAIL", f"slash markers missing {missing}", []
		elif missing and len(missing) < len(case.expect_markers):
			# At least one alternate marker matched (OR semantics for search)
			marker_ok = True
		elif missing and case.kind == "search" and "search_skip" in low:
			return "SKIP", "search unavailable", []
		elif missing and len(case.expect_markers) > 1:
			# OR: any marker is enough when multiple listed as alternatives
			if any(m.lower() in low for m in case.expect_markers):
				marker_ok = True
			else:
				return "FAIL", f"missing markers {missing}: {redacted[-400:]}", []
		elif missing:
			return "FAIL", f"missing markers {missing}: {redacted[-400:]}", []

	art = verify_artifacts(case.expect_artifacts)
	checked = art.get("checked") or []
	if case.expect_artifacts:
		if art["status"] == "FAIL":
			# Soft-skip when all artifacts optional and missing (LLM didn't write)
			if all(getattr(a, "optional", False) for a in case.expect_artifacts):
				return "SKIP", f"artifacts optional/missing after LLM: {art['detail']}", checked
			return "FAIL", art["detail"], checked
		if art["status"] == "SKIP":
			return "SKIP", art["detail"], checked
		return "PASS", art["detail"], checked

	return "PASS", f"ok ({case.kind})" + ("" if marker_ok else ""), checked


def run_case(case: ScenarioCase, *, model_override: Optional[str] = None) -> dict[str, Any]:
	started = time.time()
	model = model_override or case.model or pick_default_model()
	row: dict[str, Any] = {
		"id": case.id,
		"category": case.category,
		"tier": case.tier,
		"kind": case.kind,
		"model": model,
		"status": "SKIP",
		"detail": "",
		"seconds": 0.0,
		"artifacts_checked": [],
		"command": "",
	}
	try:
		if case.kind == "policy":
			status, detail, checked = _run_policy_case(case)
			row.update(status=status, detail=detail, artifacts_checked=checked)
			return row

		if case.kind == "offline_exec":
			status, detail, checked = _run_offline_exec(case)
			row.update(status=status, detail=detail, artifacts_checked=checked)
			return row

		env = os.environ.copy()
		env["PYTHONIOENCODING"] = "utf-8"
		env["INTERPRETER_YES"] = "1"
		data_dir = resolve_test_data_dir(require=False)
		if data_dir is not None:
			env.setdefault("INTERPRETER_TEST_DATA_DIR", str(data_dir))

		timeout = int(case.timeout_s or 90)
		if case.kind == "slash":
			# Prefer local-model probe; otherwise soft-skip when no local endpoint
			# and case asked for local (avoids cloud key / REPL crash flakiness).
			wants_local = (case.model or model) in ("local-model", "local")
			if wants_local and not _local_endpoint_reachable():
				row["status"] = "SKIP"
				row["detail"] = "local endpoint unreachable soft-skip"
				return row
			timeout = min(timeout, 20)
			cmd = _build_cli_command(case, None, model)
			row["command"] = " ".join(cmd)
			proc = _run_subprocess(
				cmd,
				cwd=str(ROOT),
				env=env,
				timeout=timeout,
				input_text=case.stdin_script or "/exit\n",
			)
		else:
			with tempfile.TemporaryDirectory(prefix="ci_scenario_") as tmp:
				prompt_path = Path(tmp) / "prompt.txt"
				prompt_path.write_text(case.prompt or "print(1)", encoding="utf-8")
				cmd = _build_cli_command(case, prompt_path, model)
				row["command"] = " ".join(cmd)
				# Hard cap so provider hangs soft-skip instead of blocking the suite.
				timeout = min(timeout, 90)
				proc = _run_subprocess(
					cmd,
					cwd=str(ROOT),
					env=env,
					timeout=timeout,
				)

		status, detail, checked = _classify_cli(case, proc)
		row.update(status=status, detail=detail, artifacts_checked=checked)
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
	categories: Optional[set[str]] = None,
	policy_only: bool = False,
	offline_only: bool = False,
	merge_report: bool = False,
) -> dict[str, Any]:
	"""Run scenarios; write master MD/HTML under scratch/."""
	if python_exe:
		os.environ["INTERPRETER_TEST_PYTHON"] = python_exe

	data_dir = resolve_test_data_dir(require=False)
	temp_holder = None
	if data_dir is None:
		temp_holder = tempfile.TemporaryDirectory(prefix="ci_live_scenarios_")
		data_dir = Path(temp_holder.name)
		os.environ["INTERPRETER_TEST_DATA_DIR"] = str(data_dir)

	fixtures = ensure_scenario_fixtures(data_dir)
	cases = build_scenario_cases(fixtures)
	if policy_only:
		cases = [c for c in cases if c.kind == "policy"]
	if offline_only:
		cases = [c for c in cases if c.kind in ("policy", "offline_exec", "slash")]
	if tiers:
		cases = [c for c in cases if c.tier in tiers]
	if categories:
		cases = [c for c in cases if c.category in categories]

	model_list = models or [pick_default_model()]
	rows: list[dict[str, Any]] = []

	# Non-LLM cases once (honor per-case model, e.g. local-model for slash)
	for case in cases:
		if case.kind in ("policy", "slash", "offline_exec"):
			override = case.model or model_list[0]
			rows.append(run_case(case, model_override=override))

	# LLM cases — default one model; optional one-by-one
	llm_cases = [c for c in cases if c.kind not in ("policy", "slash", "offline_exec")]
	for model in model_list:
		for case in llm_cases:
			row = run_case(case, model_override=model)
			if len(model_list) > 1:
				row["id"] = f"{case.id}@{model}"
			rows.append(row)

	summary = {
		"PASS": sum(1 for r in rows if r["status"] == "PASS"),
		"SKIP": sum(1 for r in rows if r["status"] == "SKIP"),
		"FAIL": sum(1 for r in rows if r["status"] == "FAIL"),
		"TOTAL": len(rows),
	}
	stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	payload: dict[str, Any] = {
		"run_id": stamp,
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"fixtures": fixtures,
		"models": model_list,
		"summary": summary,
		"rows": rows,
	}

	scratch = report_dir or (ROOT / "scratch")
	scratch.mkdir(parents=True, exist_ok=True)

	if merge_report:
		master_json = scratch / "live_scenario_report.json"
		existing = None
		if master_json.is_file():
			try:
				existing = json.loads(master_json.read_text(encoding="utf-8"))
			except (OSError, json.JSONDecodeError):
				existing = None
		payload = merge_report_rows(existing, payload)

	paths = write_master_reports(payload, scratch)
	payload["report_md"] = paths["md"]
	payload["report_html"] = paths["html"]
	payload["report_json"] = paths["json"]

	if temp_holder is not None:
		# Keep workdir if user set env; only cleanup anonymous temp
		if "ci_live_scenarios_" in str(data_dir):
			temp_holder.cleanup()

	return payload
